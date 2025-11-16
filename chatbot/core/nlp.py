from joblib import load
import os
import re, unicodedata

from core.data import get_becas, buscar_beca_por_tipo, tiene_beca, detalle_beca, find_student_by_carnet

def normalize(s: str) -> str:
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")  # quita acentos
    s = re.sub(r"[¿?¡!.,;:]", " ", s)  # quita puntuación básica
    s = re.sub(r"\s+", " ", s).strip()
    return s

MODEL_PATH = os.path.join("ml","models","intent_mlp.joblib")
_pipeline = None

CARNET_REGEX = re.compile(r"\b(20\d{2}-\d{4}I)\b", re.IGNORECASE)  # ajusta si hay otros formatos

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = load(MODEL_PATH)
    return _pipeline

def _extract_carnet(text: str):
    if not text:
        return None
    m = CARNET_REGEX.search(text)
    return m.group(1).upper() if m else None

def predecir_intencion(texto: str, umbral: float = 0.55):
    pipe = _get_pipeline()
    proba = pipe.predict_proba([texto])[0]
    clases = pipe.classes_
    idx = proba.argmax()
    intent = clases[idx]
    conf = float(proba[idx])
    if conf < umbral:
        return {"intent":"desconocido","confidence":conf}
    return {"intent":intent,"confidence":conf}

# --- NUEVO: una función de "manejo" para usar desde tu endpoint ---
def responder(texto: str, umbral: float = 0.55) -> dict:
    """
    Devuelve un dict estándar para el frontend:
    {
      "intent": "tipos_becas|requisitos_becas|estado_beca|detalle_beca|desconocido",
      "confidence": 0.92,
      "answer": "texto listo para UI",
      "data": {... opcional ...}
    }
    """
    texto_norm = normalize(texto or "")
    pred = predecir_intencion(texto_norm, umbral=umbral)
    intent = pred["intent"]; conf = pred["confidence"]

    carnet = _extract_carnet(texto)

    # Reglas de negocio suaves: si hay carnet + palabra 'beca', forzar estado/detalle
    if carnet and "beca" in texto_norm:
        if any(w in texto_norm for w in ["detalle", "cual", "cuál", "que beca", "qué beca"]):
            intent = "detalle_beca"
        else:
            intent = "estado_beca"

    # --- Intenciones:
    if intent == "tipos_becas":
        becas = get_becas()
        if not becas:
            return {"intent": intent, "confidence": conf, "answer": "No hay becas activas registradas en el sistema."}
        lista = ", ".join(b["tipo"] or (b.get("nombre") or "Beca") for b in becas)
        return {"intent": intent, "confidence": conf, "answer": f"Becas activas: {lista}."}

    if intent == "requisitos_becas":
        becas = get_becas()
        if not becas:
            return {"intent": intent, "confidence": conf, "answer": "No encuentro becas activas para listar requisitos."}
        # Muestra hasta 4, con requisitos si existen
        trozos = []
        for b in becas[:4]:
            if b["requisitos"]:
                trozos.append(f"- {b['tipo']}: " + "; ".join(b["requisitos"]))
            else:
                trozos.append(f"- {b['tipo']}")
        return {"intent": intent, "confidence": conf, "answer": "Requisitos por beca:\n" + "\n".join(trozos)}

    if intent == "estado_beca":
        if not carnet:
            return {"intent": intent, "confidence": conf, "answer": "Necesito tu carnet (formato 2021-0001I) para verificar si tienes beca."}
        st = find_student_by_carnet(carnet)
        if not st:
            return {"intent": intent, "confidence": conf, "answer": f"No encontré el carnet {carnet} en el sistema."}
        if not tiene_beca(carnet):
            nombre = st.get("fields", {}).get("nombre") or carnet
            return {"intent": intent, "confidence": conf, "answer": f"{nombre} ({carnet}) no tiene beca asignada."}
        # sí tiene
        return {"intent": intent, "confidence": conf, "answer": f"{st.get('fields',{}).get('nombre') or carnet} ({carnet}) SÍ tiene beca activa."}

    if intent == "detalle_beca":
        if not carnet:
            return {"intent": intent, "confidence": conf, "answer": "Pásame tu carnet (formato 2021-0001I) y te digo cuál beca tienes."}
        st = find_student_by_carnet(carnet)
        if not st:
            return {"intent": intent, "confidence": conf, "answer": f"No encontré el carnet {carnet} en el sistema."}
        det = detalle_beca(carnet)
        if not det:
            nombre = st.get("fields", {}).get("nombre") or carnet
            return {"intent": intent, "confidence": conf, "answer": f"{nombre} ({carnet}) no tiene beca asignada."}
        nombre = st.get("fields", {}).get("nombre") or carnet
        txt = f"{nombre} ({carnet}) tiene la beca: {det.get('beca') or '—'}."
        if det.get("porcentaje") is not None:
            txt += f" Cobertura: {det['porcentaje']}%."
        return {"intent": intent, "confidence": conf, "answer": txt, "data": det}

    # fallback
    msg = "Puedo ayudarte con: tipos de beca, requisitos o verificar por carnet si tienes beca y cuál. ¿Qué deseas consultar?"
    if conf < 0.55:
        msg = "¿Buscas tipos/requisitos de becas o deseas verificar por carnet si tienes beca?"
    return {"intent": "desconocido", "confidence": conf, "answer": msg}
