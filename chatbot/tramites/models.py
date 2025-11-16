from django.db import models
from django.utils.text import slugify

# JSONField nativo en Django 3.1+ (si usas una versión vieja con Postgres, cambia el import)
try:
    from django.db.models import JSONField
except Exception:  # pragma: no cover
    from django.contrib.postgres.fields import JSONField

class Tramite(models.Model):
    categoria = models.ForeignKey(
        'categorias.Categoria',
        on_delete=models.CASCADE,
        related_name='tramites'
    )
    titulo = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True)
    requisitos = JSONField(default=list, blank=True)  # lista de strings
    activo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('categoria', 'slug')
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['activo']),
            models.Index(fields=['categoria']),
        ]
        ordering = ['titulo']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titulo)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.titulo} ({self.categoria})'
