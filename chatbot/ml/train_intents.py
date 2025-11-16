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
    "a", "acá", "ahí", "al", "algo", "alguna", "algunas", "alguno", "algunos",
    "allá", "alli", "allí", "ambos", "ante", "antes", "aquel", "aquella",
    "aquellas", "aquello", "aquellos", "aquí", "arriba", "así", "aún", "aunque",
    "bajo", "bastante", "bien",
    "cada", "casi", "como", "con", "contra", "cual", "cuales", "cualquier",
    "cualquiera", "cuyo", "cuyos",
    "de", "debe", "deben", "debido", "del", "demás", "demasiado", "dentro", "desde",
    "donde", "dos", "durante",
    "él", "ella", "ellas", "ello", "ellos", "el", "en", "encima", "entonces",
    "entre", "era", "erais", "éramos", "eran", "eres", "es", "esa", "esas",
    "ese", "eso", "esos", "esta", "estaba", "estabais", "estábamos", "estaban",
    "estabas", "estad", "estada", "estadas", "estado", "estados", "estamos",
    "están", "estar", "estará", "estarán", "estarás", "estaré", "estaréis",
    "estaría", "estaríais", "estaríamos", "estarían", "estaría", "estas",
    "este", "estemos", "esto", "estos", "estoy", "estuve", "estuviera",
    "estuvieran", "estuviese", "estuviesen", "estuvimos", "estuviste",
    "estuvisteis", "estuvo",
    "fin", "fue", "fuera", "fueran", "fuesen", "fueron", "fui", "fuimos",
    "ha", "haber", "había", "habíais", "habíamos", "habían", "habías", "han",
    "has", "hasta", "hay", "haya", "hayan", "he",
    "hemos", "hube", "hubiera", "hubieran", "hubiese", "hubiesen", "hubimos",
    "hubiste", "hubisteis", "hubo",
    "la", "las", "le", "les", "lo", "los", "luego", "más", "me", "menos",
    "mi", "mis", "mientras", "muy",
    "nada", "ni", "ningún", "ninguna", "ninguno", "no", "nos", "nosotras",
    "nosotros", "nuestra", "nuestras",
    "nuestro", "nuestros", "nunca",
    "o", "otra", "otras", "otro", "otros",
    "para", "pero", "poco", "por", "porque", "primero", "puede", "pueden",
    "pues",
    "que", "qué", "quién", "quiénes", "quien", "quienes", "quizá",
    "se", "sea", "sean", "según", "ser", "será", "serán", "serás", "seré",
    "seréis", "sería", "seríais", "seríamos", "serían", "si", "sí",
    "sido", "siempre", "sin", "sino",
    "sobre", "solamente", "solo", "su", "sus",
    "tal", "tales", "también", "tan", "tanto", "te", "tenemos", "tener",
    "tenga", "tengan", "tengo", "ti", "tiempo", "tiene", "tienen", "toda",
    "todas", "todavía", "todo", "todos", "tras", "tu", "tus",
    "un", "una", "unas", "uno", "unos",
    "usted", "ustedes",
    "va", "vais", "valor", "vamos", "van", "varias", "varios", "vaya",
    "verdad", "vez", "vosotras", "vosotros",
    "voy",
    "y", "ya",
    "yo"
]

COMMON_TYPO_MAP = {
    # HORARIO
    "horaro": "horario",
    "orario": "horario",
    "horarrio": "horario",
    "orarrio": "horario",
    "horrario": "horario",
    "horraio": "horario",

    # BECA
    "vaca": "beca",        # error común con b/v
    "becas": "becas",
    "veca": "beca",
    "beaca": "beca",
    "bekca": "beca",

    # MONOGRAFIA
    "monogafia": "monografia",
    "monografiaa": "monografia",
    "monogrfia": "monografia",
    "monografhia": "monografia",
    "monograffia": "monografia",

    # TITULO
    "tituo": "titulo",
    "tituulo": "titulo",
    "tiltulo": "titulo",
    "titlo": "titulo",
    "titluo": "titulo",

    # BAJA
    "vaja": "baja",
    "bja": "baja",
    "bajja": "baja",
    "bajah": "baja",

    # CARNET
    "carnet": "carnet",
    "carne": "carnet",
    "carnett": "carnet",
    "carné": "carnet",
    "carnettte": "carnet",

    # GENERAL / OTROS ERRORES COMUNES
    "aplicar beca": "aplicar_beca",
    "solicitar beca": "aplicar_beca",
    "detalle beca": "detalle_beca",
    "estado beca": "estado_beca",
    "recibo beca": "donde_recibo_beca",
    "horarios estudiante": "horario_estudiante",
    "monografía": "monografia",
}


def fix_common_typos(s: str) -> str:
    """
    Reemplaza palabras clave mal escritas por su forma correcta.
    Trabaja a nivel de palabra completa (usando \b).
    """
    for wrong, right in COMMON_TYPO_MAP.items():
        # \bword\b para evitar reemplazar dentro de otras palabras
        pattern = r"\b" + re.escape(wrong) + r"\b"
        s = re.sub(pattern, right, s)
    return s

def normalize(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u00A0", " ")  # NBSP -> espacio normal
    s = s.lower()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )  # sin acentos
    s = re.sub(r"[¿?¡!.,;:]", " ", s)  # quita puntuación básica
    s = re.sub(r"\s+", " ", s).strip()
    # 👇 muy importante: corregir errores TÍPICOS de tu dominio
    s = fix_common_typos(s)
    return s

# -----------------------
# Dataset ampliado
# -----------------------
# -----------------------
# Dataset ampliado
# -----------------------

# Primero separamos las frases en dos listas:
BASE_X_TIPOS = [
    # =====================
    # Tipos de becas / apoyo económico
    # =====================
    "¿Qué becas ofrecen?",
    "tipos de becas disponibles",
    "lista de becas",
    "qué clases de becas hay",
    "categorías de becas",
    "becas activas",
    "información sobre becas disponibles",
    "qué tipos de becas hay en la universidad",
    "qué opciones de becas existen",
    "dame la lista de becas actuales",
    "qué becas puedo solicitar",
    "tipos de becas que ofrece la institución",
    "qué becas nuevas tienen",
    "qué becas están habilitadas en este periodo",
    "cuáles son las becas vigentes",
    "qué becas están disponibles ahora",
    "quiero conocer todas las becas que existen",
    "qué beneficios o becas tienen los estudiantes",
    "qué becas ofrece la universidad para primer ingreso",
    "quiero ver todas las becas activas actualmente",
    "muéstrame los tipos de becas",
    "qué becas están abiertas para aplicar",
    "qué apoyos de pago existen para estudiantes nuevos",
    "qué beneficios estudiantiles ofrecen",
    "qué becas puedo escoger este semestre",

    # Variantes sin decir solo 'beca'
    "qué programas de apoyo económico tienen para estudiantes",
    "qué ayudas económicas ofrece la universidad",
    "qué apoyos económicos hay para pagar la carrera",
    "qué beneficios de pago o descuentos tienen para estudiantes",
    "qué tipos de ayuda financiera manejan",
    "qué categorías de becas y ayudas económicas manejan",
    "qué ayudas económicas puedo solicitar",
    "qué formas de apoyo hay para estudiantes con dificultades financieras",
    "qué tipos de apoyo económico hay para continuar mis estudios",
    "qué beneficios financieros da la institución",
    "qué opciones de financiamiento tengo en la universidad",
    "qué alternativas económicas ofrecen a los estudiantes",
    "qué ayudas y descuentos están disponibles ahora",
    "qué apoyos económicos puedo pedir este semestre",
]

BASE_X_REQUISITOS = [
    # =====================
    # Requisitos de becas / ayudas económicas
    # =====================
    "¿Cuáles son los requisitos para la beca?",
    "requisitos de becas",
    "qué piden para aplicar a una beca",
    "documentos necesarios para beca",
    "condiciones para obtener una beca",
    "requisitos mínimos de becas",
    "qué se necesita para aplicar a una beca",
    "qué documentos debo entregar para beca",
    "condiciones para poder acceder a una beca",
    "qué criterios debo cumplir para beca",
    "qué requisitos académicos o administrativos se necesitan",
    "qué debo presentar para solicitar una beca",
    "qué requisitos debe cumplir un estudiante para beca",
    "cómo puedo saber si califico para una beca",
    "qué debo cumplir para que me otorguen una beca",
    "información de requisitos para becas estudiantiles",
    "documentación requerida para solicitar beca",
    "qué requisitos piden para una beca universitaria",
    "necesito saber los requisitos para becas",
    "cuáles son los pasos y requisitos para becas",

    # Variantes sin decir 'beca'
    "qué requisitos piden para las ayudas económicas",
    "qué se necesita para obtener apoyo económico",
    "qué documentos solicitan para ayuda económica",
    "qué debo cumplir para acceder a una ayuda financiera",
    "qué requisitos académicos debo tener para apoyo económico",
    "cómo saber si califico para una ayuda económica",
    "cuáles son las condiciones para obtener apoyo económico",
    "qué documentación piden para apoyo económico",
]

# BASE_X final es la unión de ambas
BASE_X = BASE_X_TIPOS + BASE_X_REQUISITOS

# Y BASE_y se calcula automáticamente para que tenga SIEMPRE la misma longitud
BASE_y = (
    ["tipos_becas"] * len(BASE_X_TIPOS)
    + ["requisitos_becas"] * len(BASE_X_REQUISITOS)
)



# -----------------------
# Bloque: aplicar_beca (MUY AMPLIADO)
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
    "informacion sobre aplicacion de becas",
    "quiero instrucciones para solicitar beca",
    "pasos para aplicar a beca de merito",
    "como postular a beca de transporte",
    "que documentos necesito para beca",
    "requisitos y formulario para beca",
    "quiero inscribirme a la beca deportiva",
    "como llenar formulario de solicitud de beca",
    "donde puedo enviar mi aplicacion de beca",
    "quiero informacion para postular a beca socioeconomica",
    "proceso completo para aplicar a beca",
    "explicame como hacer la solicitud de beca",
    "quiero solicitar beca este semestre paso a paso",
    "como hago para postular a becas disponibles",
    "ayuda con la aplicacion de beca",
    "donde se hace la solicitud de beca",
    "quiero saber los pasos para aplicar a beca",
    "como aplicar a beca sin errores",
    "quiero guía para aplicar a beca",
    "requisitos completos para solicitar beca",
    "formularios y documentos necesarios para beca",
    "quiero aplicar a beca universitaria",
    "instrucciones detalladas para aplicar a beca",
    "como postular a beca academica",
    "proceso para enviar solicitud de beca",
    "quiero conocer pasos para aplicar a beca",
    "informacion sobre becas disponibles y aplicacion",
    "como iniciar el proceso de beca",
    "donde puedo registrar mi solicitud de beca",
    "quiero saber como enviar mi formulario de beca",
    "que proceso debo seguir para una beca",
    "que pasos siguen después de aplicar a una beca",
    "como registrarme para aplicar a una beca",
]


# -----------------------
# Bloque: donde_recibo_beca (MUY AMPLIADO)
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
    "la beca llega por banco o la recojo en caja",
    "donde se procesa el pago de la beca",
    "como funciona el pago de becas",
]


# -----------------------
# Bloque: horario del estudiante (más amplio)
# -----------------------
HORARIO_BLOQ = [
    "cual es mi horario 2021-0001i",
    "que horario tengo 2021-0001i",
    "quiero saber mi horario 2021-0001i",
    "necesito mi horario de clases 2021-0001i",
    "podrias decirme mi horario mi carnet es 2021-0001i",
    "dime mi horario con carnet 2021-0001i",
    "a que grupo pertenezco 2021-0001i",
    "que grupo tengo con carnet 2021-0001i",
    "quiero saber mi grupo de clases 2021-0001i",
    "cual es mi grupo segun mi carnet 2021-0001i",
    "mostrar horario del estudiante 2021-0001i",
    "mi horario de clases es 2021-0001i",
    "consultar horario con carnet 2021-0001i",
    "saber mi horario con carnet 2021-0001i",
]


# -----------------------
# Bloques estado/detalle de beca
# -----------------------
ESTADO_BLOQ = [
    "tengo beca? mi carnet es 2021-0001i",
    "verifica si tengo beca 2021-0001i",
    "confirmar beca con carnet 2021-0001i",
    "quiero saber si tengo beca 2021-0001i",
    "consultar estado de beca 2021-0001i",
    "dime si tengo alguna beca 2021-0001i",
    "mi carnet 2021-0001i tiene beca activa?",
    "revisa si estoy asignado a alguna beca 2021-0001i",
    "estado de beca para el carnet 2021-0001i",
    "verificar si cuento con beca 2021-0001i",
    "tengo alguna beca disponible? carnet 2021-0001i",
    "comprobar beca del estudiante 2021-0001i",
    "quiero confirmar si mi beca está activa 2021-0001i",
    "estado actual de mi beca 2021-0001i",
    "mi beca está vigente? carnet 2021-0001i",
]

DETALLE_BLOQ = [
    "cual beca tengo 2021-0001i",
    "que beca tengo? carnet 2021-0001i",
    "detalle de mi beca 2021-0001i",
    "quiero saber que beca tengo 2021-0001i",
    "informacion de la beca asignada 2021-0001i",
    "que tipo de beca tengo 2021-0001i",
    "que tipo de beca tengo mi carnet es 2021-0001i",
    "que tipo de beca tengo con carnet 2021-0001i",
    "quiero saber que tipo de beca tengo 2021-0001i",
    "detalles completos de mi beca 2021-0001i",
    "información detallada de mi beca carnet 2021-0001i",
    "qué beneficios tiene mi beca 2021-0001i",
    "quiero conocer la beca que tengo 2021-0001i",
    "dime el tipo de beca que se me otorgó 2021-0001i",
    "carnet 2021-0001i, cuál es mi beca?",
    "explicación detallada de mi beca 2021-0001i",
    "información de la beca que tengo asignada 2021-0001i",
    "qué categoría de beca tengo 2021-0001i",
    "detalle de beneficios de mi beca carnet 2021-0001i",
]


# -----------------------
# Bloques: trámites académicos
# -----------------------
TRAMITE_MONOGRAFIA_BLOQ = [
    "que necesito para presentar la monografia",
    "requisitos para la monografia de graduacion",
    "cuales son los requisitos de la monografia",
    "como hago mi monografia de titulacion",
    "pasos para hacer la monografia",
    "que necesito para protocolo de monografia",
    "requisitos para protocolo monografico",
    "que necesito para la defensa de monografia",
    "que necesito para la predefensa de monografia",
    "informacion del tramite de monografia",
    "documentos necesarios para presentar la monografia",
    "guia para hacer la monografia",
    "procedimiento para entregar la monografia",
    "requisitos para la entrega final de monografia",
    "como presentar el protocolo de monografia",
    "trámites para la defensa final de la monografia",
]

TRAMITE_TITULO_BLOQ = [
    "que necesito para solicitar mi titulo universitario",
    "requisitos para tramitar el titulo universitario",
    "documentos para sacar el titulo universitario",
    "pasos para sacar el titulo de licenciado",
    "como hago el tramite del titulo universitario",
    "donde se solicita el titulo universitario",
    "quiero gestionar mi titulo universitario",
    "informacion sobre requisitos del titulo universitario",
    "que papeles piden para el titulo universitario",
    "tramite de titulo universitario",
    "proceso completo para obtener mi titulo",
    "pasos y documentos para titulo universitario",
    "quiero solicitar mi titulo profesional",
    "guia para el tramite del titulo universitario",
    "información sobre como obtener mi titulo",
]

TRAMITE_BAJA_BLOQ = [
    "como me doy de baja de la universidad",
    "quiero retirarme de la carrera",
    "tramite de baja academica",
    "que necesito para darme de baja de la universidad",
    "requisitos para baja definitiva de la carrera",
    "proceso para abandonar la carrera",
    "donde hago el tramite de baja universitaria",
    "formulario para baja de estudios universitarios",
    "como suspender temporalmente mis estudios",
    "como solicito la baja del cuatrimestre",
    "pasos para retirar mis estudios",
    "tramite para suspender temporalmente la carrera",
    "quiero darme de baja del semestre actual",
    "documentos necesarios para baja universitaria",
    "información sobre baja académica",
]


# -----------------------
# Armar X / y (siempre consistentes)
# -----------------------
# -----------------------
# Armar X / y (siempre consistentes)
# -----------------------
X = (
    list(BASE_X)
    + APLICAR_BLOQ
    + DONDE_RECIBO_BLOQ
    + ESTADO_BLOQ
    + DETALLE_BLOQ
    + TRAMITE_MONOGRAFIA_BLOQ
    + TRAMITE_TITULO_BLOQ
    + TRAMITE_BAJA_BLOQ
    + HORARIO_BLOQ
)

y = (
    list(BASE_y)
    + ["aplicar_beca"] * len(APLICAR_BLOQ)
    + ["donde_recibo_beca"] * len(DONDE_RECIBO_BLOQ)
    + ["estado_beca"] * len(ESTADO_BLOQ)
    + ["detalle_beca"] * len(DETALLE_BLOQ)
    + ["tramite_monografia"] * len(TRAMITE_MONOGRAFIA_BLOQ)
    + ["tramite_titulo"] * len(TRAMITE_TITULO_BLOQ)
    + ["tramite_baja"] * len(TRAMITE_BAJA_BLOQ)
    + ["horario_estudiante"] * len(HORARIO_BLOQ)
)



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
  ("tfidf", TfidfVectorizer(
        lowercase=True,
        analyzer="char_wb",      # 👈 n-gramas de caracteres
        ngram_range=(3,5),       # 3 a 5 caracteres, buen rango para español
        min_df=1
  )),
  ("mlp", MLPClassifier(
        hidden_layer_sizes=(32,),
        activation="relu",
        max_iter=1000,
        random_state=42
  ))
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
print(" Modelo guardado en ml/models/intent_mlp.joblib")
