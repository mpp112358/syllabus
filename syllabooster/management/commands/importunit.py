#!/usr/bin/env python
#
# Adds a command to manage.py to import a Unit from an org file.
#
# Command arguments:
# - course: the name of the course to import the unit to;
# - inputfilename: the name of the input file;
# - -u,--user: the username;
# - -t,--type: the format of the input file (currently, only org and MD are supported);
# - -n,--unitnumber: (optional) the number of the unit to import;
# - -i,--insert: (options) units will be inserted in the given positions;
# - -f,--force: don't ask for confirmation.
#
# If the course doesn't exist, it will be created. Otherwise, it will be modified.
#
# If 'unitnumber' is not given, all units will be imported.
#
# By default, the units are added in their positions
# (those specified through the :POSITION: property): If the course already has a unit with
# that position, the unit is replaced (but the user will be asked for confirmation, unless
# -f,--force is given).
#
# If -i/--insert is given, the units are inserted in their positions (shifting all subsequent
# units to a later position).
#
# Org file conventions.
#
# The org file should be structured like this (text in brackets is for explaning purposes,
# it should not appear in the file):
#
# * (Unit 1) The first unit :tag1:
#   :PROPERTIES:
#   :POSITION: 1
#   :END:
# ** (Point 1) Whatever :tag2:tag3:
#    :PROPERTIES:
#    :TYPE: theory
#    :END:
# ** (Point 2) Whatever :tag2:
# * (Unit 2) The second unit
#   :PROPERTIES:
#   :POSITION: 2
#   :END:
# ** (Point 3) Whatever
# ** (Point 4) Whatever
#
# Units MUST have a position (specified through a PROPERTY called POSITION).
#
# Units' position MUST be different.
#
# The type of a poit is specified through a PROPERTY called TYPE.
#
# Any level 1 heading is parsed as a unit.
#
# Any level 2 heading is parsed as a point.
#
# Any level > 2 heading is parsed as part of their parent's contents.
#
# Tags of units are applied to all their children points.


from pathlib import Path

import mistune
import orgparse

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max, F
from syllabooster.models import *


def renumber_points(course):
    units = Unit.objects.filter(course=course).order_by("position")
    point_number = 1
    for unit in units:
        points = CoursePoint.objects.filter(unit=unit).order_by("position")
        for point in points:
            point.position = point_number
            point.save()
            point_number = point_number + 1


def should_be_imported(unit, unitnumbers):
    if len(unitnumbers) > 0:
        return unit in unitnumbers
    return True


class Command(BaseCommand):
    help = "Imports course items from the specified file"

    def add_arguments(self, parser):
        parser.add_argument("course", help="Course name")
        parser.add_argument("inputfilename", help="Input file name")
        parser.add_argument("-u", "--user", default="manuel")
        parser.add_argument("-t", "--type", default="org", help="Input file type")
        parser.add_argument(
            "-n", "--unitnumber", type=int, help="Unit number to be imported"
        )
        parser.add_argument(
            "-i", "--insert", action="store_true", help="insert instead of replace"
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Replace course without confirmation",
        )

    def parse_org(self, input_string, unitnumbers, insert, force):
        root = orgparse.loads(input_string)
        current_unit = 0
        next_point = 1
        unit_tags = {}
        self.stdout.write(f"Unit numbers to be imported: {unitnumbers or 'all'}")
        for node in root[1:]:
            if node.level == 1:
                current_unit = int(node.get_property("POSITION"))
                node.unit = current_unit
                self.stdout.write(
                    f'Found unit "{node.heading}" with position {current_unit}'
                )
                if should_be_imported(current_unit, unitnumbers):
                    self.stdout.write(f"Position {current_unit} should be imported.")
                    if Unit.objects.filter(
                        course=self.course, position=current_unit
                    ).exists():
                        if not insert:
                            if not force:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"There is already a unit with number {current_unit} in course {self.course.name} for user {self.user.username}: it will be replaced."
                                    )
                                )
                                confirm = input(
                                    "Are you sure you want to proceed? [y/N]: "
                                )
                                if confirm.lower() not in ["y", "yes"]:
                                    self.stdout.write(self.style.ERROR("Unit skipped."))
                                    continue
                            Unit.objects.filter(
                                course=self.course, position=current_unit
                            ).delete()
                        else:
                            Unit.objects.filter(
                                course=self.course, position__gte=current_unit
                            ).update(position=F("position") + 10000)
                            Unit.objects.filter(
                                self.course, position__gte=current_unit + 10000
                            ).update(position=F("position") - 9999)

                    unit = Unit.objects.create(
                        course=self.course,
                        position=current_unit,
                        title=node.heading,
                    )
                    unit_tags[current_unit] = []
                    for tag in node.tags:
                        unit_tags[current_unit].append(tag)
            elif should_be_imported(current_unit, unitnumbers) and node.level == 2:
                point_type = node.get_property("TYPE") or "Theory"
                self.stdout.write(
                    f'Importing point "{node.heading}" of type {point_type}'
                )
                point, created = Point.objects.get_or_create(headline=node.heading)
                point.contents = node.body
                point.save()
                for tag in node.tags:
                    db_tag, created = Tag.objects.get_or_create(name=tag)
                    point.tags.add(db_tag)
                point.point_type = PointType.objects.get(name=point_type.lower())
                point.save()

                state = None
                todo = node.todo.lower()
                if todo:
                    try:
                        state = DeliveryState.objects.filter(
                            point_type_id=point.point_type.id
                        ).get(name=todo)
                    except DeliveryState.DoesNotExist:
                        state = None
                unit = None
                if not (node.parent is root):
                    unit_position = node.parent.unit
                    unit = Unit.objects.get(course=self.course, position=unit_position)
                    for tag in unit_tags[unit_position]:
                        db_tag, created = Tag.objects.get_or_create(name=tag)
                        point.tags.add(db_tag)
                    point.save()

                coursepoint = CoursePoint(
                    course=self.course,
                    point=point,
                    position=next_point,
                    state=state,
                    unit=unit,
                )
                coursepoint.save()
                next_point = next_point + 1
        renumber_points(self.course)

    def parse_md(self, input_string, unitnumbers, insert, force):
        markdown_parser = mistune.create_markdown(renderer=None)
        ast = markdown_parser(input_string)
        print(ast)

    def handle(self, *args, **options):

        user = options["user"]
        self.user = None
        try:
            self.user = User.objects.get(username=user)
        except User.DoesNotExist:
            raise CommandError('User "%s" does not exist' % user)
        course_name = options["course"]
        self.course, created = Course.objects.get_or_create(
            name=course_name, user=self.user
        )
        inputfilename = options["inputfilename"]
        inputfilepath = Path(inputfilename)
        if not inputfilepath.is_file():
            raise CommandError('File "%s" not found' % inputfilename)
        with open(inputfilepath, "r") as mdfile:
            input_string = mdfile.read()
        self.unitnumbers = []
        if options["unitnumber"]:
            self.unitnumbers = [options["unitnumber"]]
        input_format = options["type"]
        if input_format == "md":
            self.parse_md(
                input_string, self.unitnumbers, options["insert"], options["force"]
            )
        elif input_format == "org":
            self.parse_org(
                input_string, self.unitnumbers, options["insert"], options["force"]
            )
