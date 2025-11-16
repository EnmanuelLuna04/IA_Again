# core/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

import json, re

from .nlp import predecir_intencion
from .data import (
    get_becas,
    buscar_beca_por_tipo,
    find_student_by_carnet,
    tiene_beca,
    detalle_beca,
)

CARNET_REGEX = re.compile(r"\b(20\d{2}-\d{4}I)\b", re.IGNORECASE)

def _extract_carnet(text: str):
    if not text:
        return None
    m = CARNET_REGEX.search(text)
    return m.group(1).upper() if m else None

def _get_request_data(request):
    """
    Soporta tanto DRF Request (request.data) como WSGIRequest (leer JSON del body).
    """
    # DRF Request
    if hasattr(request, "data"):
        return request.data

    # WSGIRequest: intentar JSON en el body
    try:
        body = (request.body or b"").decode("utf-8").strip()
        if body:
            return json.loads(body)
    except Exception:
        pass

    # fallback a POST/GET
    if hasattr(request, "POST") and request.POST:
        return request.POST
    if hasattr(request, "GET") and request.GET:
        return request.GET

    return {}

@api_view(["POST"])              # si DRF está instalado, convierte a Request
@permission_classes([AllowAny])
def nlp_intent(request):
    data = _get_request_data(request)
    q = (data or {}).get("query", "")
    if not isinstance(q, str):
        q = str(q or "")
    q = q.strip()

    if not q:
        return Response({"detail": "query requerido"}, status=status.HTTP_400_BAD_REQUEST)
    
    ql = q.lower()
    carnet = _extract_carnet(q)

    # Si la frase indica estado/detalle de beca, forzamos la intención,
    # y si no hay carnet devolvemos el mensaje pidiéndolo.
    if any(p in ql for p in ["tengo beca", "estado de beca", "ver si tengo beca"]):
        if not carnet:
            return Response({
                "query": q, "intent": "estado_beca", "confidence": 1.0,
                "answer": {"mensaje": "Necesito tu carnet (formato 2021-0001I) para verificar si tienes beca."}
            }, status=200)

    if any(p in ql for p in ["cual beca tengo", "qué beca tengo", "que beca tengo", "detalle de mi beca"]):
        if not carnet:
            return Response({
                "query": q, "intent": "detalle_beca", "confidence": 1.0,
                "answer": {"mensaje": "Pásame tu carnet (formato 2021-0001I) y te digo cuál beca tienes."}
            }, status=200)


    pred = predecir_intencion(q)
    intent = pred.get("intent", "desconocido")
    confidence = float(pred.get("confidence", 0.0))
    payload = {"query": q, "intent": intent, "confidence": round(confidence, 3)}

    # ajuste suave por carnet + palabra 'beca'
    carnet = _extract_carnet(q)
    q_lower = q.lower()
    if carnet and "beca" in q_lower:
        if any(w in q_lower for w in ["detalle", "cuál", "cual", "qué beca", "que beca"]):
            intent = "detalle_beca"
        else:
            intent = "estado_beca"
        payload["intent"] = intent

    if intent == "tipos_becas":
        tipos = [b["tipo"] or (b.get("nombre") or "Beca") for b in get_becas()]
        payload["answer"] = {"tipos_becas": tipos}

    elif intent == "requisitos_becas":
        candidatos = buscar_beca_por_tipo(q)
        if candidatos:
            payload["answer"] = {
                "becas": [{"tipo": b["tipo"], "requisitos": b["requisitos"]} for b in candidatos]
            }
        else:
            payload["answer"] = {
                "requisitos_por_beca": {b["tipo"]: b["requisitos"] for b in get_becas()}
            }

    elif intent == "estado_beca":
        if not carnet:
            payload["answer"] = {"mensaje": "Necesito tu carnet (formato 2021-0001I) para verificar si tienes beca."}
        else:
            st = find_student_by_carnet(carnet)
            if not st:
                payload["answer"] = {"mensaje": f"No encontré el carnet {carnet} en el sistema."}
            else:
                tiene = tiene_beca(carnet)
                nombre = st.get("fields", {}).get("nombre") or carnet
                if not tiene:
                    payload["answer"] = {"estado_beca": {"tiene_beca": False, "carnet": carnet, "nombre": nombre}}
                else:
                    info = detalle_beca(carnet) or {}
                    payload["answer"] = {
                        "estado_beca": {
                            "tiene_beca": True,
                            "carnet": carnet,
                            "nombre": nombre,
                            "periodo": info.get("periodo"),
                            "estado": info.get("estado"),
                            "activo": info.get("activo", False),
                        }
                    }

    # elif intent == "aplicar_beca":
    #     # ¿menciona un tipo?
    #     candidatos = buscar_beca_por_tipo(q)
    #     if candidatos:
    #         # Devolver requisitos de esa(s) beca(s), tu UI ya sabe mostrarlos
    #         payload["answer"] = {
    #             "becas": [{"tipo": b["tipo"], "requisitos": b["requisitos"]} for b in candidatos]
    #         }
    #     else:
    #         # No mencionó tipo: pedir que elija, devolviendo lista (reutilizas scholarship-options)
    #         tipos = [b["tipo"] or (b.get("nombre") or "Beca") for b in get_becas()]
    #         payload["answer"] = {
    #             "mensaje": "¿Por cuál beca te gustaría aplicar? Elige una para ver los pasos:",
    #             "tipos_becas": tipos
    #         }

    elif intent == "aplicar_beca":
        candidatos = buscar_beca_por_tipo(q)
        if candidatos:
            payload["answer"] = {"becas": [{"tipo": b["tipo"], "requisitos": b["requisitos"]} for b in candidatos]}
        else:
            tipos = [b["tipo"] or (b.get("nombre") or "Beca") for b in get_becas()]
            payload["answer"] = {"mensaje": "¿Por cuál beca te gustaría aplicar? Elige una:", "tipos_becas": tipos}

    elif intent == "donde_recibo_beca":
        payload["answer"] = {"mensaje": "La beca se recibe en Caja o puede ser depositada (según tu asignación).", "metodos_entrega": ["Caja", "Depósito"]}

    
    elif intent == "detalle_beca":
        if not carnet:
            payload["answer"] = {"mensaje": "Pásame tu carnet (formato 2021-0001I) y te digo cuál beca tienes."}
        else:
            st = find_student_by_carnet(carnet)
            if not st:
                payload["answer"] = {"mensaje": f"No encontré el carnet {carnet} en el sistema."}
            else:
                info = detalle_beca(carnet)
                nombre = st.get("fields", {}).get("nombre") or carnet
                if not info:
                    payload["answer"] = {"detalle_beca": {"tiene_beca": False, "carnet": carnet, "nombre": nombre}}
                else:
                    payload["answer"] = {
                        "detalle_beca": {
                            "tiene_beca": True,
                            "carnet": carnet,
                            "nombre": nombre,
                            "beca": info.get("beca"),
                            "porcentaje": info.get("porcentaje"),
                            "periodo": info.get("periodo"),
                            "estado": info.get("estado"),
                            "activo": info.get("activo", False),
                        }
                    }

    else:
        payload["answer"] = {
            "mensaje": "No estoy seguro. ¿Te interesan tipos de becas/requisitos o verificar por carnet si tienes beca?"
        }

    return Response(payload, status=200)
