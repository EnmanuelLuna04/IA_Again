from django.db import models
from categorias.models import Categoria
from students.models import Student

class Beca(models.Model):
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="becas"
    )
    tipo = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    requisitos = models.TextField()
    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.tipo


class AsignacionBeca(models.Model):
    class Estado(models.TextChoices):
        ASIGNADA = "asignada", "Asignada"
        ACTIVA = "activa", "Activa"
        SUSPENDIDA = "suspendida", "Suspendida"
        FINALIZADA = "finalizada", "Finalizada"
        RECHAZADA = "rechazada", "Rechazada"

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="asignaciones_beca"
    )
    beca = models.ForeignKey(
        Beca, on_delete=models.PROTECT, related_name="asignaciones"
    )
    periodo = models.CharField(max_length=40, help_text="Ej. I Semestre 2025")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ASIGNADA)
    fecha_asignacion = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    monto_mensual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "beca", "periodo")
        ordering = ("-activo", "student__carnet", "beca__tipo")
        indexes = [
            models.Index(fields=["student", "activo", "estado"]),
            models.Index(fields=["periodo"]),
        ]

    def __str__(self):
        return f"{self.student.carnet} - {self.beca.tipo} ({self.periodo})"
