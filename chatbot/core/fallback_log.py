# core/fallback_log.py
from pathlib import Path
from datetime import datetime
from django.conf import settings
import json

# Ruta del archivo donde guardaremos los fallbacks
# Puedes cambiarla si quieres, por ejemplo a una carpeta "logs/"
DEFAULT_LOG_PATH = Path(settings.BASE_DIR) / "fallback_queries.jsonl"

LOG_PATH = Path(getattr(settings, "FALLBACK_LOG_PATH", DEFAULT_LOG_PATH))


def log_fallback(query: str, intent: str, confidence: float, meta: dict | None = None):
  """
  Guarda en un archivo .jsonl (una línea por registro) las consultas
  que la neurona no entendió bien o que consideramos 'fallback'.
  """
  try:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    entry = {
      "timestamp": datetime.utcnow().isoformat(),
      "query": query,
      "intent": intent,
      "confidence": round(float(confidence or 0.0), 3),
      "meta": meta or {},
    }

    with LOG_PATH.open("a", encoding="utf-8") as f:
      f.write(json.dumps(entry, ensure_ascii=False) + "\n")

  except Exception:
    # No queremos que un fallo de log rompa la API
    pass
