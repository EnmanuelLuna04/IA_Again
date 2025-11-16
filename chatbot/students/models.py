from django.db import models

class Student(models.Model):
    nombre = models.CharField(max_length=120)
    carnet = models.CharField(max_length=20, unique=True)

    # 🔵 Nuevo: grupo principal y secundario
    grupo_principal = models.CharField(max_length=20)
    grupo_secundario = models.CharField(max_length=20, blank=True, null=True)

    anio_actual = models.PositiveSmallIntegerField(help_text="Año que cursa actualmente")
    tiene_beca = models.BooleanField(default=False)  # NUEVO

    def __str__(self):
        return f"{self.nombre} ({self.carnet})"


class Clase(models.Model):
    nombre = models.CharField(max_length=120)
    codigo = models.CharField(max_length=20, unique=True)
    anio_correspondiente = models.PositiveSmallIntegerField(help_text="Año al que pertenece la clase")

    def __str__(self):
        return f"{self.nombre} ({self.anio_correspondiente}° año)"


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="inscripciones")
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="inscripciones")
    periodo = models.CharField(max_length=20, help_text="Ej. I Semestre 2025")
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "clase", "periodo")

    def __str__(self):
        return f"{self.student.nombre} - {self.clase.nombre} ({self.periodo})"
