# horarios/models.py
from django.db import models
from django.core.validators import RegexValidator
from django.db.models import Q
from django.utils import timezone

GROUP_CODE_RE = r'^[1-5][MT][1-2]$'  # p.ej.: 1M1, 4T2, 5T1

class Horario(models.Model):
    group_code = models.CharField(
        max_length=8,
        db_index=True,
        validators=[RegexValidator(GROUP_CODE_RE)],
        help_text="Código de grupo (ej. 1M1, 4T2, 5T1)."
    )
    titulo = models.CharField(max_length=180)
    periodo = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    content_type = models.CharField(max_length=100, default='image/jpeg')
    original_filename = models.CharField(max_length=255)
    imagen = models.BinaryField()
    activo = models.BooleanField(default=True)

    # 👉 IMPORTANTE: default=timezone.now para que loaddata NO falle con raw=True
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['group_code', 'periodo'],
                condition=Q(activo=True),
                name='uniq_horario_activo_por_grupo_y_periodo',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.group_code:
            self.group_code = self.group_code.strip().upper().replace(' ', '')
        super().save(*args, **kwargs)

    def __str__(self):
        per = f" - {self.periodo}" if self.periodo else ""
        return f"{self.group_code}{per}: {self.titulo}"
