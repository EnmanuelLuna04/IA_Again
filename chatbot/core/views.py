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
    get_tramites_monografia,
    get_tramite_titulo_universitario,
    get_tramite_baja_universidad,
    get_horario_estudiante,  # ← coma extra corregida
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

    # WSGIRequest: intentar JSON del body
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


@api_view(["POST"])
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

    # ─────────────────────────────────────────────
    # Forzar intención: estado_beca
    # ─────────────────────────────────────────────
    if any(p in ql for p in ["tengo beca", "estado de beca", "ver si tengo beca"]):
        if not carnet:
            return Response({
                "query": q,
                "intent": "estado_beca",
                "confidence": 1.0,
                "answer": {
                    "mensaje": "Necesito tu carnet (formato 2021-0001I) para verificar si tienes beca."
                }
            }, status=200)

    # Forzar intención: detalle_beca
    if any(p in ql for p in ["cual beca tengo", "qué beca tengo", "que beca tengo", "detalle de mi beca"]):
        if not carnet:
            return Response({
                "query": q,
                "intent": "detalle_beca",
                "confidence": 1.0,
                "answer": {
                    "mensaje": "Pásame tu carnet (formato 2021-0001I) y te digo cuál beca tienes."
                }
            }, status=200)

    # ─────────────────────────────────────────────
    # Predicción NLP
    # ─────────────────────────────────────────────
    pred = predecir_intencion(q)
    intent = pred.get("intent", "desconocido")
    confidence = float(pred.get("confidence", 0.0))

    payload = {
        "query": q,
        "intent": intent,
        "confidence": round(confidence, 3),
    }

    # Ajuste inteligente por carnet + palabra "beca"
    carnet = _extract_carnet(q)
    q_lower = q.lower()

    if carnet and "beca" in q_lower:
        if any(w in q_lower for w in ["detalle", "cuál", "cual", "qué beca", "que beca"]):
            intent = "detalle_beca"
        else:
            intent = "estado_beca"
        payload["intent"] = intent

    # ─────────────────────────────────────────────
    # INTENCIONES
    # ─────────────────────────────────────────────

    # TIPOS DE BECAS
    if intent == "tipos_becas":
        tipos = [b["tipo"] or (b.get("nombre") or "Beca") for b in get_becas()]
        payload["answer"] = {"tipos_becas": tipos}

    # REQUISITOS DE BECAS
    elif intent == "requisitos_becas":
        candidatos = buscar_beca_por_tipo(q)
        if candidatos:
            payload["answer"] = {
                "becas": [
                    {"tipo": b["tipo"], "requisitos": b["requisitos"]}
                    for b in candidatos
                ]
            }
        else:
            payload["answer"] = {
                "requisitos_por_beca": {
                    b["tipo"]: b["requisitos"] for b in get_becas()
                }
            }

    # ESTADO DE BECA
    elif intent == "estado_beca":
        if not carnet:
            payload["answer"] = {
                "mensaje": (
                    "Pásame tu carnet (formato 2021-0001I) y te digo si tienes beca "
                    "y de qué tipo."
                )
            }
        else:
            st = find_student_by_carnet(carnet)
            if not st:
                payload["answer"] = {"mensaje": f"No encontré el carnet {carnet} en el sistema."}
            else:
                info = detalle_beca(carnet)
                nombre = st.get("fields", {}).get("nombre") or carnet

                if not info:
                    payload["answer"] = {
                        "estado_beca": {
                            "tiene_beca": False,
                            "carnet": carnet,
                            "nombre": nombre,
                        }
                    }
                else:
                    payload["answer"] = {
                        "estado_beca": {
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

    # APLICAR A BECA
    elif intent == "aplicar_beca":
        candidatos = buscar_beca_por_tipo(q)

        if candidatos:
            payload["answer"] = {
                "becas": [
                    {"tipo": b["tipo"], "requisitos": b["requisitos"]}
                    for b in candidatos
                ]
            }
        else:
            tipos = [b["tipo"] or (b.get("nombre") or "Beca") for b in get_becas()]
            payload["answer"] = {
                "mensaje": "¿Por cuál beca te gustaría aplicar? Elige una:",
                "tipos_becas": tipos,
            }

    # DÓNDE RECIBO BECA
    elif intent == "donde_recibo_beca":
        payload["answer"] = {
            "mensaje": "La beca se recibe según tu asignación (pago en Caja o Depósito bancario).",
            "metodos_entrega": ["Caja", "Depósito"],
        }

    # DETALLE DE BECA
    elif intent == "detalle_beca":
        if not carnet:
            payload["answer"] = {
                "mensaje": "Pásame tu carnet (formato 2021-0001I) y te digo cuál beca tienes."
            }
        else:
            st = find_student_by_carnet(carnet)
            if not st:
                payload["answer"] = {"mensaje": f"No encontré el carnet {carnet} en el sistema."}
            else:
                info = detalle_beca(carnet)
                nombre = st.get("fields", {}).get("nombre") or carnet

                if not info:
                    payload["answer"] = {
                        "detalle_beca": {
                            "tiene_beca": False,
                            "carnet": carnet,
                            "nombre": nombre,
                        }
                    }
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

    
    elif intent == "horario_estudiante":
        if not carnet:
            payload["answer"] = {
                "mensaje": "Pásame tu carnet (formato 2021-0001I) y te muestro tu grupo y horarios."
            }
        else:
            info = get_horario_estudiante(carnet)
            if not info:
                payload["answer"] = {
                    "mensaje": f"No encontré el carnet {carnet} en el sistema."
                }
            else:
                grupos = info.get("grupos") or []
                tiene_algún_horario = any((g.get("horarios") for g in grupos))

                if not grupos:
                    payload["answer"] = {
                        "horario": {
                            "tiene_horario": False,
                            "carnet": info["carnet"],
                            "nombre": info["nombre"],
                            "grupo": None,
                            "mensaje": "No encontré ningún grupo asignado para este estudiante.",
                            "grupos": [],
                        }
                    }
                elif not tiene_algún_horario:
                    payload["answer"] = {
                        "horario": {
                            "tiene_horario": False,
                            "carnet": info["carnet"],
                            "nombre": info["nombre"],
                            "grupo": info["grupo"],
                            "mensaje": "Tienes grupo, pero no encontré horarios registrados para tus grupos.",
                            "grupos": grupos,  # igual devolvemos los grupos sin horarios
                        }
                    }
                else:
                    h = info.get("horario")  # horario principal (puede ser del primer grupo)
                    payload["answer"] = {
                        "horario": {
                            "tiene_horario": True,
                            "carnet": info["carnet"],
                            "nombre": info["nombre"],
                            # principal
                            "grupo": info["grupo"],
                            "periodo": h.get("periodo") if h else None,
                            "titulo": h.get("titulo") if h else None,
                            "horario_id": h.get("pk") if h else None,
                            "archivo": h.get("original_filename") if h else None,
                            # todos los grupos
                            "grupos": grupos,
                        }
                    }


    # =========================
    # NUEVOS INTENTS: TRÁMITES
    # =========================
    elif intent == "tramite_monografia":
        tramites = get_tramites_monografia()
        if not tramites:
            payload["answer"] = {
                "mensaje": "Por ahora no tengo registrados los requisitos de monografía. Te recomiendo consultar en Registro Académico."
            }
        else:
            # Devolvemos todos los trámites relacionados: protocolo, predefensa y defensa
            payload["answer"] = {
                "tramite": "monografia",
                "tramites": [
                    {
                        "titulo": t["titulo"],
                        "slug": t["slug"],
                        "descripcion": t["descripcion"],
                        "requisitos": t["requisitos"],
                    }
                    for t in tramites
                ],
            }

    elif intent == "tramite_titulo":
        tramite = get_tramite_titulo_universitario()
        if not tramite:
            payload["answer"] = {
                "mensaje": "Por ahora no tengo registrados los requisitos para el título universitario. Te recomiendo consultar en Registro Académico."
            }
        else:
            payload["answer"] = {
                "tramite": "titulo_universitario",
                "titulo": tramite["titulo"],
                "slug": tramite["slug"],
                "descripcion": tramite["descripcion"],
                "requisitos": tramite["requisitos"],
            }

    elif intent == "tramite_baja":
        tramite = get_tramite_baja_universidad()
        if not tramite:
            payload["answer"] = {
                "mensaje": "Por ahora no tengo registrado el proceso de baja. Te recomiendo consultar en Registro Académico."
            }
        else:
            payload["answer"] = {
                "tramite": "baja_universidad",
                "titulo": tramite["titulo"],
                "slug": tramite["slug"],
                "descripcion": tramite["descripcion"],
                "requisitos": tramite["requisitos"],
            }

    else:
        payload["answer"] = {
            "mensaje": (
                "No estoy seguro. ¿Te interesan tipos de becas/requisitos, "
                "trámites de título/monografía/baja o verificar por carnet si tienes beca?"
            )
        }

    return Response(payload, status=200)



