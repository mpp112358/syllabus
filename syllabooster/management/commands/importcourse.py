#!/usr/bin/env python
#
# Adds a command to manage.py to import a Course from an org file.
#
# Command arguments:
# - course: the name of the course to import;
# - inputfilename: the name of the input file;
# - -t,--type: the format of the input file (currently, only org and MD are supported).
# - -f,--force: don't ask for confirmation before overwriting an existing course
#
# If the course exists, it will be overwritten, but the user will be asked for confirmation
# unless -f,--format is given.
#
# Org file conventions.
#
# The org file should be structured like this (text in brackets is for explaning purposes,
# it should not appear in the file):
#
# * (Unit 1) The first unit :tag1:
# ** (Point 1) Whatever :tag2:tag3:
#    :PROPERTIES:
#    :TYPE: theory
#    :END:
# ** (Point 2) Whatever :tag2:
# * (Unit 2) The second unit
# ** (Point 3) Whatever
# ** (Point 4) Whatever
#
# Numbering will happen automatically: units are numbered in the order they appear in the file,
# and points are numbered in the order they appear in the file independently of the unit they
# belong to.
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
from django.db.models import Max
from syllabooster.models import *


class Command(BaseCommand):
    help = "Imports course items from the specified file"

    def add_arguments(self, parser):
        parser.add_argument("course", help="Course name")
        parser.add_argument("inputfilename", help="Input file name")
        parser.add_argument("-u", "--user", default="manuel")
        parser.add_argument("-t", "--type", default="org", help="Input file type")
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Replace course without confirmation",
        )

    def parse_org(self, input_string):
        root = orgparse.loads(input_string)
        current_unit = 0
        next_point = 1
        unit_tags = {}
        for node in root[1:]:
            if node.level == 1:
                current_unit = current_unit + 1
                node.unit = current_unit
                unit = Unit.objects.create(
                    course=self.course, position=current_unit, title=node.heading
                )
                unit_tags[current_unit] = []
                for tag in node.tags:
                    unit_tags[current_unit].append(tag)
            elif node.level == 2:
                point, created = Point.objects.get_or_create(headline=node.heading)
                point.contents = node.body
                point.save()
                for tag in node.tags:
                    db_tag, created = Tag.objects.get_or_create(name=tag)
                    point.tags.add(db_tag)
                point_type = node.get_property("TYPE") or "Theory"
                point.point_type = PointType.objects.get(name=point_type)
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

    def parse_md(self, input_string):
        markdown_parser = mistune.create_markdown(renderer=None)
        ast = markdown_parser(input_string)
        print(ast)

    def handle(self, *args, **options):
        # If there's already a course with the given name, it will be deleted.
        # Then a new one is created.

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
        if Course.objects.filter(name=course_name, user=self.user).exists():
            if not options["force"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"Course {course_name} for user {user} already exists and will be replaced."
                    )
                )
                confirm = input("Are you sure you want to proceed? [y/N]: ")
                if confirm.lower() not in ["y", "yes"]:
                    self.stdout.write(self.style.ERROR("Operation cancelled."))
                    return
            Course.objects.filter(name=course_name, user=self.user).delete()

        self.course = Course.objects.create(name=course_name, user=self.user)

        inputfilename = options["inputfilename"]
        inputfilepath = Path(inputfilename)
        if not inputfilepath.is_file():
            raise CommandError('File "%s" not found' % inputfilename)
        with open(inputfilepath, "r") as mdfile:
            input_string = mdfile.read()
        input_format = options["type"]
        if input_format == "md":
            self.parse_md(input_string)
        elif input_format == "org":
            self.parse_org(input_string)
