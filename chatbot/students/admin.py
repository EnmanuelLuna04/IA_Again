from django.contrib import admin
from .models import Student, Clase, Enrollment

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("nombre", "carnet", "grupo_principal", "grupo_secundario", "anio_actual", "tiene_beca")
    search_fields = ("nombre", "carnet", "grupo_principal", "grupo_secundario")
    list_filter = ("anio_actual", "tiene_beca")  # filtrar por beca


@admin.register(Clase)
class ClaseAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "anio_correspondiente")
    search_fields = ("codigo", "nombre")
    list_filter = ("anio_correspondiente",)

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "clase", "periodo", "activo")
    list_filter = ("periodo", "activo", "clase__anio_correspondiente")
    search_fields = ("student__nombre", "student__carnet", "clase__nombre", "clase__codigo")
