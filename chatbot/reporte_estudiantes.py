import os
import django

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chatbot.settings")  # Ajusta según tu proyecto
django.setup()

from students.models import Student
from becas.models import AsignacionBeca

# Traer los primeros 10 estudiantes que tengan asignaciones de beca activas
estudiantes_con_beca = Student.objects.filter(
    asignaciones_beca__activo=True
).distinct()[:10]

for s in estudiantes_con_beca:
    # Obtener los tipos de beca distintos del estudiante
    tipos_beca = s.asignaciones_beca.filter(activo=True).values_list("beca__tipo", flat=True).distinct()
    
    print(f"Estudiante: {s.nombre} ({s.carnet})")
    print("Tipos de beca:", ", ".join(tipos_beca))
    print("-" * 40)
