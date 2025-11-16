from django.contrib import admin
from .models import Beca, AsignacionBeca

@admin.register(Beca)
class BecaAdmin(admin.ModelAdmin):
    list_display = ("tipo", "categoria", "activa")
    list_filter = ("categoria", "activa")
    search_fields = ("tipo", "descripcion", "requisitos")
    ordering = ("tipo",)

@admin.register(AsignacionBeca)
class AsignacionBecaAdmin(admin.ModelAdmin):
    list_display = ("student", "beca", "periodo", "estado", "activo", "fecha_asignacion", "fecha_fin", "monto_mensual")
    list_filter = ("estado", "activo", "periodo", "beca__tipo")
    search_fields = ("student__nombre", "student__carnet", "beca__tipo")
    ordering = ("-activo", "student__carnet")
