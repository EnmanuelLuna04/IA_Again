from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from joblib import dump
from collections import Counter
import json, os
import re, unicodedata

SPANISH_STOPWORDS = [
    "de","la","que","el","en","y","a","los","del","se","las","por","un","para",
    "con","no","una","su","al","lo","como","más","pero","sus","le","ya","o","este",
    "sí","porque","esta","entre","cuando","muy","sin","sobre","también","me","hasta",
    "hay","donde","quien","desde","todo","nos","durante","todos","uno","les"
]

def normalize(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u00A0", " ")  # NBSP -> espacio normal (copias/pegados)
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")  # sin acentos
    s = re.sub(r"[¿?¡!.,;:]", " ", s)  # quita puntuación básica
    s = re.sub(r"\s+", " ", s).strip()
    return s

# -----------------------
# Dataset semilla
# -----------------------
BASE_X = [
  "¿Qué becas ofrecen?", "tipos de becas disponibles", "lista de becas",
  "qué clases de becas hay", "categorías de becas", "becas activas",
  "¿Cuáles son los requisitos para la beca?", "requisitos de becas",
  "qué piden para aplicar a una beca", "documentos necesarios para beca",
  "condiciones para obtener una beca", "requisitos mínimos de becas",
]
BASE_y = [
  "tipos_becas","tipos_becas","tipos_becas",
  "tipos_becas","tipos_becas","tipos_becas",
  "requisitos_becas","requisitos_becas",
  "requisitos_becas","requisitos_becas",
  "requisitos_becas","requisitos_becas",
]

# -----------------------
# Bloque: aplicar_beca
# -----------------------
APLICAR_BLOQ = [
    "como aplico a una beca",
    "como puedo aplicar a la beca",
    "pasos para solicitar una beca",
    "requisitos para aplicar a la beca",
    "quiero aplicar a una beca",
    "donde hago la solicitud de beca",
    "como hacer la solicitud de beca",
    "proceso de aplicacion a becas",
    "tramites para conseguir beca",
    "como postulo a la beca",
    "documentos para aplicar a la beca",
    "como me inscribo a una beca",
    "quiero postular a beca socioeconomica",
    "quiero aplicar a la beca de merito",
    "aplicar a beca deportiva",
    "como aplicar a beca socioeconomica",
    "quiero solicitar una beca este semestre",
    "pasos para postular a becas disponibles",
    "ayuda para aplicar a una beca",
    "formulario para solicitud de beca",
    "como aplicar a la beca de transporte",
    "me explicas como aplicar a una beca",
    "que debo hacer para aplicar a beca",
    "donde envio mi solicitud de beca",
    "como aplicar a beca este periodo",
    "como aplicar a cualquier beca",
    "proceso para pedir una beca",
    "como aplicar y que me pidan",
    "quiero saber como aplicar",
    "aplicar beca requisitos y pasos",
]

# -----------------------
# Bloque: donde_recibo_beca (caja o depósito)
# -----------------------
DONDE_RECIBO_BLOQ = [
    "donde puedo recibir la beca",
    "donde cobran la beca",
    "la beca se paga en caja o deposito",
    "la beca me la depositan o la retiro en caja",
    "donde me entregan la beca",
    "forma de pago de la beca",
    "metodo de cobro de la beca",
    "medio de pago de la beca",
    "la beca es depositada o en caja",
    "como recibo el dinero de la beca",
    "por donde recibo la beca",
    "pago de la beca en caja o banco",
    "donde retiro la beca",
    "la beca se deposita",
    "es en caja o depositada la beca",
    "el cobro de la beca es en caja o por deposito",
    "la beca me llega por transferencia o tengo que pasar a caja",
    "recibo la beca por banco o en tesoreria",
    "se cobra la beca en ventanilla o por deposito",
    "la ayuda economica se paga en caja o bancaria",
    "el apoyo economico me lo depositan o lo cobro en caja",
    "donde hacen efectivo el pago de la beca",
    "me depositan la beca a mi cuenta",
    "la beca viene por transferencia bancaria",
    "donde paso a retirar la beca",
    "la beca la entregan en caja",
    "la beca es por deposito bancario",
    "cobro de beca en caja o por banco",
    "como es el desembolso de la beca",
    "donde se acredita la beca",
    "pago de beca por deposito o efectivo",
    "la beca se recibe en caja de la universidad",
    "la beca se recibe por deposito a tarjeta o cuenta",
    "tesoreria paga la beca o la depositan",
    "la beca la dan en ventanilla",
    "es deposito o retiro en caja la beca",
    "como me entregan la beca, caja o deposito",
    "el pago de la beca es en caja",
    "el pago de la beca es por deposito",
    "me pueden depositar la beca",
    "tengo que ir a caja para cobrar la beca",
]

# -----------------------
# Bloques: estado/detalle por carnet
# -----------------------
ESTADO_BLOQ = [
  "tengo beca? mi carnet es 2021-0001i",
  "verifica si tengo beca 2021-0001i",
  "confirmar beca con carnet 2021-0001i",
  "quiero saber si tengo beca 2021-0001i",
  "consultar estado de beca 2021-0001i",
]
DETALLE_BLOQ = [
  "cual beca tengo 2021-0001i",
  "que beca tengo? carnet 2021-0001i",
  "detalle de mi beca 2021-0001i",
  "quiero saber que beca tengo 2021-0001i",
  "informacion de la beca asignada 2021-0001i",
]

# -----------------------
# Armar X / y (siempre consistentes)
# -----------------------
X = list(BASE_X) + APLICAR_BLOQ + DONDE_RECIBO_BLOQ + ESTADO_BLOQ + DETALLE_BLOQ
y = list(BASE_y) + \
    ["aplicar_beca"] * len(APLICAR_BLOQ) + \
    ["donde_recibo_beca"] * len(DONDE_RECIBO_BLOQ) + \
    ["estado_beca"] * len(ESTADO_BLOQ) + \
    ["detalle_beca"] * len(DETALLE_BLOQ)

# -----------------------
# Sanity checks
# -----------------------
if len(X) != len(y):
    raise ValueError(f"X({len(X)}) y y({len(y)}) tienen longitudes distintas. Revisa los bloques añadidos.")

dist = Counter(y)
clases_con_1 = [c for c, n in dist.items() if n < 2]
use_stratify = not bool(clases_con_1)
if clases_con_1:
    print("⚠️ Las siguientes clases tienen menos de 2 ejemplos:", clases_con_1)
    print("   Se desactiva 'stratify' para evitar errores en el split.")

# Normalización opcional previa (el Tfidf ya hace lowercase; mantener por si quieres forzar)
X_norm = [normalize(t) for t in X]

# -----------------------
# Split
# -----------------------
if use_stratify:
    X_train, X_test, y_train, y_test = train_test_split(
        X_norm, y, test_size=0.25, random_state=42, stratify=y
    )
else:
    X_train, X_test, y_train, y_test = train_test_split(
        X_norm, y, test_size=0.25, random_state=42
    )

# -----------------------
# Pipeline y entrenamiento
# -----------------------
pipeline = Pipeline([
  ("tfidf", TfidfVectorizer(lowercase=True, stop_words=SPANISH_STOPWORDS,
                            ngram_range=(1,2), min_df=1)),
  ("mlp", MLPClassifier(hidden_layer_sizes=(16,), activation="relu",
                        max_iter=400, random_state=42))
])

pipeline.fit(X_train, y_train)
print(classification_report(y_test, pipeline.predict(X_test)))

# -----------------------
# Guardado de artefactos
# -----------------------
os.makedirs("ml/models", exist_ok=True)
dump(pipeline, "ml/models/intent_mlp.joblib")
with open("ml/models/labels.json","w",encoding="utf-8") as f:
    json.dump(sorted(set(y)), f, ensure_ascii=False, indent=2)
print("✅ Modelo guardado en ml/models/intent_mlp.joblib")
