# core/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .fallback_log import log_fallback


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
    get_horario_estudiante,
)

CARNET_REGEX = re.compile(r"\b(20\d{2}-\d{4}I)\b", re.IGNORECASE)
INTENT_MIN_CONFIDENCE = 0.55  # umbral para considerar confiable una intención


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


def _has_domain_keyword(ql: str) -> bool:
    """
    Palabras clave del dominio que nos interesan (becas, horarios, trámites...).
    Si el texto no contiene nada de esto, es probable que sea saludo / charla general.
    """
    keywords = [
        "beca",
        "becas",
        "horario",
        "horarios",
        "grupo",
        "clase",
        "clases",
        "monografia",
        "monografía",
        "titulo",
        "título",
        "tramite",
        "trámite",
        "baja",
        "matricula",
        "matrícula",
        "registro",
    ]
    return any(k in ql for k in keywords)


def _is_smalltalk(ql: str) -> bool:
    """
    Detecta saludos y charla general (hola, buenas, etc.) SIN palabras del dominio.
    """
    greetings = [
        "hola",
        "buenas",
        "buenos dias",
        "buenos días",
        "buenas tardes",
        "buenas noches",
        "que tal",
        "qué tal",
        "hey",
        "ola",
        "hi",
        "hello",
    ]
    if any(ql.startswith(g) or ql == g for g in greetings) and not _has_domain_keyword(ql):
        return True
    return False


DOMAIN_INTENTS = {
    "tipos_becas",
    "requisitos_becas",
    "estado_beca",
    "detalle_beca",
    "aplicar_beca",
    "donde_recibo_beca",
    "horario_estudiante",
    "tramite_monografia",
    "tramite_titulo",
    "tramite_baja",
}


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
    # 0) SALUDOS / CHARLA GENERAL
    # ─────────────────────────────────────────────
    if _is_smalltalk(ql):
        payload = {
            "query": q,
            "intent": "saludo",
            "confidence": 1.0,
            "answer": {
                "mensaje": (
                    "¡Hola! 👋 Puedo ayudarte con:\n"
                    "• Becas (tipos, requisitos, si tienes beca, etc.)\n"
                    "• Horarios y grupo según tu carnet\n"
                    "• Trámites de monografía, título y baja\n\n"
                    "Por ejemplo, puedes preguntar:\n"
                    "» ¿Qué tipos de beca hay?\n"
                    "» ¿Cuáles son los requisitos de la beca monetaria?\n"
                    "» ¿Cuál es mi grupo según mi carnet 2021-0001I?"
                )
            },
        }
        return Response(payload, status=200)

    # ─────────────────────────────────────────────
    # 1) Forzar intención: estado_beca (sin carnet)
    # ─────────────────────────────────────────────
    if any(p in ql for p in ["tengo beca", "estado de beca", "ver si tengo beca"]):
        if not carnet:
            return Response(
                {
                    "query": q,
                    "intent": "estado_beca",
                    "confidence": 1.0,
                    "answer": {
                        "mensaje": "Necesito tu carnet (formato 2021-0001I) para verificar si tienes beca."
                    },
                },
                status=200,
            )

    # 2) Forzar intención: detalle_beca (sin carnet)
    if any(p in ql for p in ["cual beca tengo", "qué beca tengo", "que beca tengo", "detalle de mi beca"]):
        if not carnet:
            return Response(
                {
                    "query": q,
                    "intent": "detalle_beca",
                    "confidence": 1.0,
                    "answer": {
                        "mensaje": "Pásame tu carnet (formato 2021-0001I) y te digo cuál beca tienes."
                    },
                },
                status=200,
            )

    # ─────────────────────────────────────────────
    # 3) Predicción NLP
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
    # 4) FILTRO DE CONFIANZA / DOMINIO
    # ─────────────────────────────────────────────
    # Si la neurona dice que es un intent de nuestro dominio (becas, horarios, trámites...)
    # pero:
    #   - la confianza es baja, o
    #   - el texto ni siquiera menciona palabras del dominio,
    # entonces NO lo tomamos como válido y respondemos algo genérico.
    if intent in DOMAIN_INTENTS and (
        confidence < INTENT_MIN_CONFIDENCE or not _has_domain_keyword(ql)
    ):
         # Logueamos este caso como ejemplo de fallback
        log_fallback(
            query=q,
            intent=intent,
            confidence=confidence,
            meta={
                "reason": "low_conf_or_no_domain",
                "domain_intent": True,
            },
        )
        payload["intent"] = "desconocido"
        payload["answer"] = {
            "mensaje": (
                "No estoy seguro de haber entendido tu consulta.\n\n"
                "Puedo ayudarte con:\n"
                "• Becas (tipos, requisitos, si tienes beca, etc.)\n"
                "• Horarios y grupo según tu carnet\n"
                "• Trámites de monografía, título y baja\n\n"
                "Por ejemplo:\n"
                "» ¿Qué tipos de beca hay?\n"
                "» ¿Cuáles son los requisitos del trámite de título universitario?\n"
                "» ¿Cuál es mi grupo según mi carnet 2021-0001I?"
            )
        }
        return Response(payload, status=200)

    # ─────────────────────────────────────────────
    # 5) INTENCIONES PRINCIPALES
    # ─────────────────────────────────────────────

    # TIPOS DE BECAS
    if intent == "tipos_becas":
        tipos = [b["tipo"] or (b.get("nombre") or "Beca") for b in get_becas()]
        payload["answer"] = {
            "mensaje": "Tenemos disponibles los siguientes tipos de becas:",
            "tipos_becas": tipos,
        }

    # REQUISITOS DE BECAS
    elif intent == "requisitos_becas":
        candidatos = buscar_beca_por_tipo(q)
        if candidatos:
            payload["answer"] = {
                "mensaje": "Estos son los requisitos de la beca que consultaste:",
                "becas": [
                    {"tipo": b["tipo"], "requisitos": b["requisitos"]}
                    for b in candidatos
                ],
            }
        else:
            payload["answer"] = {
                "mensaje": "No entendí qué beca específica deseas. Te muestro los tipos disponibles:",
                "requisitos_por_beca": {
                    b["tipo"]: b["requisitos"] for b in get_becas()
                },
            }

    # ESTADO DE BECA
    elif intent == "estado_beca":
        if not carnet:
            payload["answer"] = {
                "mensaje": "Pásame tu carnet (formato 2021-0001I) y te digo si tienes beca y de qué tipo."
            }
        else:
            st = find_student_by_carnet(carnet)
            if not st:
                payload["answer"] = {
                    "mensaje": f"No encontré el carnet {carnet} en el sistema."
                }
            else:
                info = detalle_beca(carnet)
                nombre = st.get("fields", {}).get("nombre") or carnet

                if not info:
                    payload["answer"] = {
                        "mensaje": f"{nombre} ({carnet}), no tienes una beca asignada.",
                        "estado_beca": {
                            "tiene_beca": False,
                            "carnet": carnet,
                            "nombre": nombre,
                        },
                    }
                else:
                    payload["answer"] = {
                        "mensaje": f"{nombre} ({carnet}), tienes una beca asignada.",
                        "estado_beca": {
                            "tiene_beca": True,
                            "carnet": carnet,
                            "nombre": nombre,
                            "beca": info.get("beca"),
                            "porcentaje": info.get("porcentaje"),
                            "periodo": info.get("periodo"),
                            "estado": info.get("estado"),
                            "activo": info.get("activo", False),
                        },
                    }

    # APLICAR A BECA
    elif intent == "aplicar_beca":
        candidatos = buscar_beca_por_tipo(q)

        if candidatos:
            payload["answer"] = {
                "mensaje": "Estos son los requisitos para aplicar a la beca que mencionaste:",
                "becas": [
                    {"tipo": b["tipo"], "requisitos": b["requisitos"]}
                    for b in candidatos
                ],
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
            "mensaje": "La beca se recibe según tu asignación (pago en Caja o depósito bancario).",
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
                payload["answer"] = {
                    "mensaje": f"No encontré el carnet {carnet} en el sistema."
                }
            else:
                info = detalle_beca(carnet)
                nombre = st.get("fields", {}).get("nombre") or carnet

                if not info:
                    payload["answer"] = {
                        "mensaje": f"{nombre} ({carnet}), no tienes una beca asignada.",
                        "detalle_beca": {
                            "tiene_beca": False,
                            "carnet": carnet,
                            "nombre": nombre,
                        },
                    }
                else:
                    payload["answer"] = {
                        "mensaje": f"{nombre} ({carnet}), este es el detalle de tu beca:",
                        "detalle_beca": {
                            "tiene_beca": True,
                            "carnet": carnet,
                            "nombre": nombre,
                            "beca": info.get("beca"),
                            "porcentaje": info.get("porcentaje"),
                            "periodo": info.get("periodo"),
                            "estado": info.get("estado"),
                            "activo": info.get("activo", False),
                        },
                    }

    # HORARIO ESTUDIANTE
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
                nombre = info.get("nombre") or carnet

                if not grupos:
                    payload["answer"] = {
                        "mensaje": (
                            f"{nombre} ({carnet}), no encontré ningún grupo asignado "
                            "para este estudiante."
                        ),
                        "horario": {
                            "tiene_horario": False,
                            "carnet": info["carnet"],
                            "nombre": nombre,
                            "grupo": None,
                            "mensaje": "No encontré ningún grupo asignado para este estudiante.",
                            "grupos": [],
                        },
                    }
                elif not tiene_algún_horario:
                    payload["answer"] = {
                        "mensaje": (
                            f"{nombre} ({carnet}), tienes grupo asignado pero no encontré "
                            "horarios registrados para tus grupos."
                        ),
                        "horario": {
                            "tiene_horario": False,
                            "carnet": info["carnet"],
                            "nombre": nombre,
                            "grupo": info.get("grupo"),
                            "mensaje": "Tienes grupo, pero no encontré horarios registrados para tus grupos.",
                            "grupos": grupos,
                        },
                    }
                else:
                    h = info.get("horario")  # horario principal
                    payload["answer"] = {
                        "mensaje": f"{nombre} ({carnet}), estos son tus grupos y horarios.",
                        "horario": {
                            "tiene_horario": True,
                            "carnet": info["carnet"],
                            "nombre": nombre,
                            "grupo": info.get("grupo"),
                            "periodo": h.get("periodo") if h else None,
                            "titulo": h.get("titulo") if h else None,
                            "horario_id": h.get("pk") if h else None,
                            "archivo": h.get("original_filename") if h else None,
                            "grupos": grupos,
                        },
                    }

    # TRÁMITES: MONOGRAFÍA
    elif intent == "tramite_monografia":
        tramites = get_tramites_monografia()
        if not tramites:
            payload["answer"] = {
                "mensaje": (
                    "Por ahora no tengo registrados los requisitos de monografía. "
                    "Te recomiendo consultar en Registro Académico."
                )
            }
        else:
            payload["answer"] = {
                "mensaje": "Aquí tienes los trámites y requisitos relacionados con la monografía.",
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

    # TRÁMITE: TÍTULO
    elif intent == "tramite_titulo":
        tramite = get_tramite_titulo_universitario()
        if not tramite:
            payload["answer"] = {
                "mensaje": (
                    "Por ahora no tengo registrados los requisitos para el título universitario. "
                    "Te recomiendo consultar en Registro Académico."
                )
            }
        else:
            payload["answer"] = {
                "mensaje": "Estos son los requisitos para el trámite de título universitario.",
                "tramite": "titulo_universitario",
                "titulo": tramite["titulo"],
                "slug": tramite["slug"],
                "descripcion": tramite["descripcion"],
                "requisitos": tramite["requisitos"],
            }

    # TRÁMITE: BAJA
    elif intent == "tramite_baja":
        tramite = get_tramite_baja_universidad()
        if not tramite:
            payload["answer"] = {
                "mensaje": (
                    "Por ahora no tengo registrado el proceso de baja. "
                    "Te recomiendo consultar en Registro Académico."
                )
            }
        else:
            payload["answer"] = {
                "mensaje": "Estos son los requisitos para el trámite de baja de la universidad.",
                "tramite": "baja_universidad",
                "titulo": tramite["titulo"],
                "slug": tramite["slug"],
                "descripcion": tramite["descripcion"],
                "requisitos": tramite["requisitos"],
            }

    # INTENCIÓN DESCONOCIDA / FALLBACK
    else:
         # Logueamos también el fallback general
        log_fallback(
            query=q,
            intent=intent,
            confidence=confidence,
            meta={
                "reason": "final_fallback",
                "domain_intent": intent in DOMAIN_INTENTS,
            },
        )
        payload["answer"] = {
            "mensaje": (
                "No estoy seguro de haber entendido tu consulta.\n\n"
                "Puedo ayudarte con:\n"
                "• Becas (tipos, requisitos, si tienes beca, etc.)\n"
                "• Horarios y grupo según tu carnet\n"
                "• Trámites de monografía, título y baja\n\n"
                "Por ejemplo:\n"
                "» ¿Qué tipos de beca hay?\n"
                "» ¿Cuáles son los requisitos del trámite de título universitario?\n"
                "» ¿Cuál es mi grupo según mi carnet 2021-0001I?"
            )
        }

    return Response(payload, status=200)