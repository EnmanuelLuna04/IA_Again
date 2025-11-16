from django.contrib import admin
from .models import Tramite

@admin.register(Tramite)
class TramiteAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'activo', 'updated_at')
    list_filter = ('categoria', 'activo')
    search_fields = ('titulo', 'descripcion')
    prepopulated_fields = {"slug": ("titulo",)}
