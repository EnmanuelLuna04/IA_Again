# --- NUEVO/ACTUALIZADO EN core/data.py ---

from django.conf import settings
from pathlib import Path
from functools import lru_cache
import json, re

# Rutas de fixtures
FIXTURE_CANDIDATES = [
    Path(settings.BASE_DIR) / "becas" / "fixtures" / "becas.json",
]
TRAMITES_FIXTURE = Path(settings.BASE_DIR) / "tramites" / "fixtures" / "tramites.json"


STUDENTS_FIXTURE = Path(settings.BASE_DIR) / "students" / "fixtures" / "students.json"
ASIG_FIXTURE     = Path(settings.BASE_DIR) / "becas" / "fixtures" / "asignaciones_becas.json"
HORARIOS_FIXTURE = Path(settings.BASE_DIR) / "horarios" / "fixtures" / "horarios.json"


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


@lru_cache
def _load_horarios_raw():
    """
    Carga el fixture horarios/fixtures/horarios.json.
    Si no existe, devuelve lista vacía.
    """
    if not HORARIOS_FIXTURE.exists():
        return []
    with open(HORARIOS_FIXTURE, "r", encoding="utf-8") as f:
        return json.load(f)


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

#Tramites
@lru_cache
def _load_tramites_raw():
    """
    Carga el fixture tramites/fixtures/tramites.json.
    Si no existe, devuelve lista vacía.
    """
    if not TRAMITES_FIXTURE.exists():
        return []
    with open(TRAMITES_FIXTURE, "r", encoding="utf-8") as f:
        return json.load(f)
    
def _normalize_tramite_raw(item):
    """
    Convierte un item crudo del fixture de tramites en un dict listo para usar en el chatbot.

    Estructura resultante:
    {
        "pk": int,
        "categoria": int,
        "titulo": str,
        "slug": str,
        "descripcion": str,
        "requisitos": [str],
        "activo": bool,
    }
    """
    if not item:
        return None
    fields = item.get("fields", {}) or {}
    return {
        "pk": item.get("pk"),
        "categoria": fields.get("categoria"),
        "titulo": (fields.get("titulo") or "").strip(),
        "slug": (fields.get("slug") or "").strip(),
        "descripcion": (fields.get("descripcion") or "").strip(),
        # en tu fixture ya viene como lista de strings
        "requisitos": list(fields.get("requisitos") or []),
        "activo": bool(fields.get("activo", True)),
    }


def _normalize_horario(item):
    """
    Convierte un item crudo del fixture de horarios en un dict liviano,
    sin incluir el binario de la imagen.
    """
    if not item:
        return None
    fields = item.get("fields", {}) or {}
    return {
        "pk": item.get("pk"),
        "group_code": (fields.get("group_code") or "").strip().upper(),
        "titulo": (fields.get("titulo") or "").strip(),
        "periodo": (fields.get("periodo") or "").strip(),
        "activo": bool(fields.get("activo", True)),
        "original_filename": (fields.get("original_filename") or "").strip() or None,
    }


# -------------------------------------------------
# HORARIOS (basados en horarios/fixtures/horarios.json)
# -------------------------------------------------

def get_horarios(activos_only: bool = True):
    """
    Devuelve la lista de horarios normalizados.

    Cada horario es:
    {
        "pk": int,
        "group_code": str,
        "titulo": str,
        "periodo": str,
        "activo": bool,
        "original_filename": str | None,
    }
    """
    resultados = []
    for item in _load_horarios_raw():
        h = _normalize_horario(item)
        if not h:
            continue
        if activos_only and not h["activo"]:
            continue
        resultados.append(h)
    return resultados


def _horarios_index_by_group_code():
    """
    Índice interno: group_code -> [items crudos]
    """
    idx = {}
    for item in _load_horarios_raw():
        fields = item.get("fields", {}) or {}
        group_code = (fields.get("group_code") or "").strip().upper()
        if group_code:
            idx.setdefault(group_code, []).append(item)
    return idx


def buscar_horarios_por_group_code(group_code: str):
    """
    Devuelve la lista de horarios para un código de grupo (ej. 5T1),
    ordenando primero los activos y, dentro de ellos, del pk más reciente al más viejo.
    """
    if not group_code:
        return []
    group_code = group_code.strip().upper()
    idx = _horarios_index_by_group_code()
    items = idx.get(group_code, [])
    if not items:
        return []

    activos = []
    inactivos = []
    for it in items:
        f = it.get("fields", {}) or {}
        if f.get("activo", True):
            activos.append(it)
        else:
            inactivos.append(it)

    activos.sort(key=lambda it: it.get("pk", 0), reverse=True)
    inactivos.sort(key=lambda it: it.get("pk", 0), reverse=True)

    return [_normalize_horario(it) for it in (activos + inactivos)]


def get_horario_estudiante(carnet: str):
    """
    Dado un carnet, devuelve:
    - carnet, nombre
    - grupo principal (si existe)
    - horario principal (el más reciente/activo del primer grupo)
    - todos los grupos y sus horarios asociados

    Estructura:
    {
      "carnet": "2021-0001I",
      "nombre": "Juan Pérez",
      "grupo": "5T1" | None,
      "horario": { ... } | None,
      "grupos": [
        {
          "grupo": "5T1",
          "horarios": [ { ... }, { ... } ]
        },
        {
          "grupo": "5P1",
          "horarios": [ { ... } ]
        }
      ]
    }
    """
    if not carnet:
        return None

    st = find_student_by_carnet(carnet)
    if not st:
        return None

    sfields = st.get("fields", {}) or {}
    nombre = sfields.get("nombre") or carnet
    grupos = _get_grupos_from_student_fields(sfields)

    # Si no tiene grupos registrados
    if not grupos:
        return {
            "carnet": carnet.upper(),
            "nombre": nombre,
            "grupo": None,
            "horario": None,
            "grupos": [],
        }

    grupos_detalle = []
    horario_principal = None

    for idx, g in enumerate(grupos):
        horarios_g = buscar_horarios_por_group_code(g)  # ya normalizados
        grupos_detalle.append({
            "grupo": g,
            "horarios": horarios_g,
        })

        # Primer grupo + primer horario activo lo usamos como principal
        if idx == 0 and horarios_g:
            horario_principal = horarios_g[0]

    return {
        "carnet": carnet.upper(),
        "nombre": nombre,
        "grupo": grupos[0],          # primer grupo como principal
        "horario": horario_principal,  # puede ser None
        "grupos": grupos_detalle,    # todos los grupos con sus horarios
    }


def _get_grupos_from_student_fields(sfields: dict):
    """
    Extrae y normaliza los grupos de un estudiante.
    Soporta campos como 'grupo_principal' y 'grupo_secundario'.
    Devuelve una lista sin duplicados, en mayúsculas.
    """
    grupos = []
    for key in ("grupo_principal", "grupo_secundario"):
        g = (sfields.get(key) or "").strip().upper()
        if g and g not in grupos:
            grupos.append(g)
    return grupos


def _normalize_tramite_raw(item):
    """
    Convierte un item crudo del fixture de tramites en un dict listo para usar en el chatbot.

    Estructura resultante:
    {
        "pk": int,
        "categoria": int,
        "titulo": str,
        "slug": str,
        "descripcion": str,
        "requisitos": [str],
        "activo": bool,
    }
    """
    if not item:
        return None
    fields = item.get("fields", {}) or {}
    return {
        "pk": item.get("pk"),
        "categoria": fields.get("categoria"),
        "titulo": (fields.get("titulo") or "").strip(),
        "slug": (fields.get("slug") or "").strip(),
        "descripcion": (fields.get("descripcion") or "").strip(),
        
        "requisitos": list(fields.get("requisitos") or []),
        "activo": bool(fields.get("activo", True)),
    }


def detalle_beca(carnet: str):
    asg = buscar_asignacion_por_carnet(carnet)
    return resumen_asignacion(asg) if asg else None


# -------------------------------------------------
# TRÁMITES ACADÉMICOS (basados en tramites/fixtures/tramites.json)
# -------------------------------------------------

def get_tramites(activos_only: bool = True, categoria: int | None = None):
    """
    Devuelve la lista de trámites normalizados desde el fixture.

    Cada trámite es:
    {
        "pk": int,
        "categoria": int,
        "titulo": str,
        "slug": str,
        "descripcion": str,
        "requisitos": [str],
        "activo": bool,
    }
    """
    tramites = []
    for item in _load_tramites_raw():
        t = _normalize_tramite_raw(item)
        if not t:
            continue
        if activos_only and not t["activo"]:
            continue
        if categoria is not None and t["categoria"] != categoria:
            continue
        tramites.append(t)
    return tramites


def _tramites_index_by_slug():
    """
    Índice interno por slug (ej: 'tramite-titulo-universitario', 'protocolo-monografico', etc.).
    """
    idx = {}
    for item in _load_tramites_raw():
        fields = item.get("fields", {}) or {}
        slug = (fields.get("slug") or "").lower()
        if slug:
            idx[slug] = item
    return idx


def get_tramite_by_slug(slug: str):
    """
    Devuelve UN trámite (normalizado) por su slug exacto.
    Ejemplos de slug según tu fixture:
      - 'tramite-titulo-universitario'
      - 'protocolo-monografico'
      - 'defensa-monografica'
      - 'predefensa-monografica'
      - 'baja-universidad'
    """
    if not slug:
        return None
    raw = _tramites_index_by_slug().get(slug.lower())
    return _normalize_tramite_raw(raw) if raw else None


def buscar_tramites_por_texto(query: str, categoria: int | None = None):
    """
    Búsqueda simple en título, slug, descripción y requisitos.

    Útil si luego quieres implementar cosas como:
      - 'buscame cualquier trámite que hable de monografía'
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    resultados = []
    for t in get_tramites(activos_only=True, categoria=categoria):
        texto = " ".join([
            t.get("titulo") or "",
            t.get("slug") or "",
            t.get("descripcion") or "",
            " ".join(t.get("requisitos") or []),
        ]).lower()
        if q in texto:
            resultados.append(t)
    return resultados


# Helpers específicos para los tres grupos que te interesan:
#   - monografía (protocolo, predefensa, defensa)
#   - título universitario
#   - baja de la universidad

_MONOGRAFIA_SLUGS = {
    "protocolo-monografico",
    "predefensa-monografica",
    "defensa-monografica",
}


def get_tramites_monografia():
    """
    Devuelve TODOS los trámites relacionados con monografía:
    protocolo, predefensa y defensa (según slugs del fixture).
    """
    return [
        t for t in get_tramites()
        if (t.get("slug") or "").lower() in _MONOGRAFIA_SLUGS
    ]


def get_tramite_titulo_universitario():
    """
    Devuelve el trámite principal de título universitario.
    """
    return get_tramite_by_slug("tramite-titulo-universitario")


def get_tramite_baja_universidad():
    """
    Devuelve el trámite de baja académica.
    """
    return get_tramite_by_slug("baja-universidad")
