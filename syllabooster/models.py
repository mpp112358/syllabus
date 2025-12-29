from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class Tag(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return str(self.name)


class PointType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return str(self.name)


class DeliveryState(models.Model):
    point_type = models.ForeignKey(
        PointType, on_delete=models.CASCADE, related_name="states", null=True
    )
    position = models.PositiveIntegerField(null=True)
    name = models.CharField(max_length=50)
    display_name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    css_class = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ["point_type", "name"]

    def __str__(self):
        return f"{self.point_type.name}:{self.display_name}"


class Point(models.Model):
    headline = models.CharField(max_length=200)
    contents = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag)
    point_type = models.ForeignKey(
        PointType, on_delete=models.PROTECT, related_name="points", null=True
    )

    def __str__(self):
        return str(self.headline)


class Syllabus(models.Model):
    name = models.CharField(max_length=100)
    points = models.ManyToManyField(Point, through="SyllabusPoint")

    def __str__(self):
        return str(self.name)


class SyllabusPoint(models.Model):
    syllabus = models.ForeignKey(Syllabus, on_delete=models.CASCADE)
    point = models.ForeignKey(Point, on_delete=models.CASCADE)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position"]
        unique_together = ["syllabus", "point"]

    def __str__(self):
        return f"{self.syllabus}:{self.position}:{self.point}"


class Course(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    points = models.ManyToManyField(Point, through="CoursePoint")
    current_position = models.PositiveIntegerField(db_default=0)  # type: ignore[call-arg]

    class Meta:
        unique_together = ["name", "user"]

    def __str__(self):
        return str(self.name)


class Unit(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=50)

    class Meta:
        ordering = ["position"]
        unique_together = ["course", "position"]

    def __str__(self):
        return f"({self.course.user.username}:{self.course}) Unit {self.position}: {self.title}"


class CoursePoint(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    point = models.ForeignKey(Point, on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    state = models.ForeignKey(
        DeliveryState, on_delete=models.PROTECT, related_name="course_points", null=True
    )
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        ordering = ["position"]
        unique_together = ["course", "point"]

    def __str__(self):
        return f"{self.course}:{self.position}:{self.point}"
