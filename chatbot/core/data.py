# --- NUEVO/ACTUALIZADO EN core/data.py ---

from django.conf import settings
from pathlib import Path
from functools import lru_cache
import json, re

# Rutas de fixtures
FIXTURE_CANDIDATES = [
    Path(settings.BASE_DIR) / "becas" / "fixtures" / "becas.json",
]
STUDENTS_FIXTURE = Path(settings.BASE_DIR) / "students" / "fixtures" / "students.json"
ASIG_FIXTURE     = Path(settings.BASE_DIR) / "becas" / "fixtures" / "asignaciones_becas.json"

@lru_cache
def _load_becas_raw():
    for p in FIXTURE_CANDIDATES:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"No encontré el fixture: {FIXTURE_CANDIDATES[0]}")

@lru_cache
def _load_students_raw():
    if not STUDENTS_FIXTURE.exists():
        return []
    with open(STUDENTS_FIXTURE, "r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache
def _load_asignaciones_raw():
    if not ASIG_FIXTURE.exists():
        return []
    with open(ASIG_FIXTURE, "r", encoding="utf-8") as f:
        return json.load(f)

def _normalize_requisitos(text: str):
    if not text:
        return []
    lines = [re.sub(r"^\s*-\s*", "", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]

def get_becas():
    """
    Devuelve: [{"pk": int, "tipo": str, "descripcion": str, "requisitos": [str], "activa": bool, "nombre": str?}]
    Solo incluye las activas (activa=True) si el campo existe (fallback a True si no está).
    """
    raw = _load_becas_raw()
    becas = []
    for it in raw:
        fields = it.get("fields", {}) or {}
        activa = fields.get("activa", True)  # si tu fixture no trae 'activa', asumimos True
        if not activa:
            continue
        becas.append({
            "pk": it.get("pk"),
            "tipo": (fields.get("tipo") or fields.get("nombre") or "").strip(),
            "descripcion": (fields.get("descripcion") or "").strip(),
            "requisitos": _normalize_requisitos(fields.get("requisitos", "")),
            "activa": True,
            "nombre": (fields.get("nombre") or "").strip(),
        })
    return becas

def buscar_beca_por_tipo(query: str):
    """
    Busca becas por tipo/nombre (match flexible, case-insensitive).
    Retorna una lista de dicts tal como los produce get_becas().
    """
    q = (query or "").lower()
    candidatos = []
    for b in get_becas():
        t = (b.get("tipo") or "").lower()
        n = (b.get("nombre") or "").lower()
        if (q and (q in t or t in q)) or (n and (q in n or n in q)):
            candidatos.append(b)
    return candidatos


def _beca_index_by_pk():
    idx = {}
    for it in _load_becas_raw():
        idx[it.get("pk")] = it
    return idx

def _student_index_by_pk():
    idx = {}
    for it in _load_students_raw():
        idx[it.get("pk")] = it
    return idx

def _student_index_by_carnet():
    idx = {}
    for it in _load_students_raw():
        fields = it.get("fields", {}) or {}
        carnet = (fields.get("carnet") or "").upper()
        if carnet:
            idx[carnet] = it
    return idx

def find_student_by_carnet(carnet: str):
    if not carnet:
        return None
    return _student_index_by_carnet().get(carnet.upper())

def _get_beca_nombre_from_pk(beca_pk: int):
    """
    Intenta devolver un nombre legible de beca:
    1) fields.tipo
    2) fields.nombre
    3) 'Beca <pk>' como fallback
    """
    braw = _beca_index_by_pk().get(beca_pk)
    if not braw:
        return f"Beca {beca_pk}"
    fields = braw.get("fields", {}) or {}
    return (fields.get("tipo") or fields.get("nombre") or f"Beca {beca_pk}").strip()

def get_asignaciones():
    return _load_asignaciones_raw()

def _asignaciones_de_student_pk(student_pk: int):
    """
    Filtra asignaciones por student pk, y prioriza las activas.
    Ordena por pk descendente como heurística de "más reciente".
    """
    asigns = []
    for it in get_asignaciones():
        f = it.get("fields", {}) or {}
        if f.get("student") == student_pk:
            asigns.append(it)
    if not asigns:
        return []
    # primero activas al frente
    asigns.sort(key=lambda it: ((it.get("fields", {}) or {}).get("activo", False), it.get("pk", 0)), reverse=True)
    return asigns

def buscar_asignacion_por_carnet(carnet: str):
    """
    Busca la mejor asignación para el carnet:
    - Resuelve pk del student desde students.json
    - Filtra asignaciones por ese pk
    - Elige la activa más reciente (pk mayor), si ninguna activa, la más reciente
    """
    st = find_student_by_carnet(carnet)
    if not st:
        return None
    student_pk = st.get("pk")
    cand = _asignaciones_de_student_pk(student_pk)
    return cand[0] if cand else None

def resumen_asignacion(it_asign):
    """
    Convierte una asignación cruda del fixture en dict listo para UI.
    Incluye: beca (nombre), periodo, estado, activo, porcentaje (si existiera).
    """
    if not it_asign:
        return None
    f = it_asign.get("fields", {}) or {}
    beca_nombre = _get_beca_nombre_from_pk(f.get("beca")) if f.get("beca") is not None else None
    return {
        "beca": beca_nombre,
        "periodo": f.get("periodo"),
        "estado": f.get("estado"),
        "activo": f.get("activo", False),
        "porcentaje": f.get("porcentaje"),  # por si luego agregas este campo
    }

def tiene_beca(carnet: str) -> bool:
    asg = buscar_asignacion_por_carnet(carnet)
    if not asg:
        return False
    f = asg.get("fields", {}) or {}
    # Consideramos "tiene beca" si está activa y activa=True
    return bool(f.get("activo", False) and (f.get("estado", "") or "").lower() == "activa")

def detalle_beca(carnet: str):
    asg = buscar_asignacion_por_carnet(carnet)
    return resumen_asignacion(asg) if asg else None
