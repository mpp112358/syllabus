from django.contrib import admin

from .models import (
    Tag,
    PointType,
    DeliveryState,
    Point,
    Syllabus,
    SyllabusPoint,
    Course,
    CoursePoint,
    Unit,
)

# Register your models here.

admin.site.register(Tag)
admin.site.register(PointType)
admin.site.register(DeliveryState)
admin.site.register(Point)
admin.site.register(Syllabus)
admin.site.register(SyllabusPoint)
admin.site.register(Course)
admin.site.register(CoursePoint)
admin.site.register(Unit)
