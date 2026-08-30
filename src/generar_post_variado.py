"""
Genera el post diario del Radar Fantasy con un formato distinto según
el día de la semana. Se ejecuta DESPUÉS de motor_diario_v3_3.py y
sobrescribe datos/post_diario_v3_3.txt con la versión final que se
envía por correo / se publica en X.

No modifica ninguna fórmula del modelo V3.3: solo lee los CSV que
motor_diario_v3_3.py ya generó (ranking_actual_v3_3.csv,
memoria_v3_3.csv) y redacta el texto en lenguaje sencillo, apto para
cualquier edad (sin tecnicismos tipo "score" o "var_7d").

Además consulta TheSportsDB (API gratuita, sin necesidad de clave
propia) para saber si hoy es día de jornada de LaLiga o cuántos días
faltan para la próxima. Si esa consulta falla por lo que sea
(sin internet, API caída, etc.), el post se genera igual, solo que
sin la frase de la jornada — nunca rompe la automatización.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "datos"
RANKING_FILE = DATA_DIR / "ranking_actual_v3_3.csv"
MEMORIA_FILE = DATA_DIR / "memoria_v3_3.csv"
POST_FILE = DATA_DIR / "post_diario_v3_3.txt"

HASHTAGS = "#LaLigaFantasy #Fantasy #LaLiga"

# Límite de X sin cuenta Premium (280 caracteres). Dejamos margen de
# seguridad para el contador "(n/N)" que se añade a cada tweet del hilo.
LIMITE_TWEET = 280
MARGEN_CONTADOR = 10

POSICIONES = {1: "🧤 Portero", 2: "🛡️ Defensa", 3: "⚙️ Centrocampista", 4: "⚽ Delantero"}

# ID de LaLiga en TheSportsDB y clave pública gratuita (no requiere registro)
LALIGA_ID = "4335"
THESPORTSDB_KEY = "123"
THESPORTSDB_URL = f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}/eventsnextleague.php?id={LALIGA_ID}"


# ------------------------------------------------------------------
# Etiquetas sencillas en vez de "score" numérico
# ------------------------------------------------------------------
def etiqueta(score):
    if score >= 55:
        return "🔥🔥🔥 Muy recomendado"
    if score >= 45:
        return "🔥🔥 Recomendado"
    return "🔥 Para vigilar"


# ------------------------------------------------------------------
# Información de la jornada (best-effort, nunca rompe el script)
# ------------------------------------------------------------------
def obtener_info_jornada():
    try:
        resp = requests.get(THESPORTSDB_URL, timeout=8)
        resp.raise_for_status()
        eventos = (resp.json() or {}).get("events") or []
        if not eventos:
            return None
        primero = eventos[0]
        fecha_partido = datetime.strptime(primero["dateEvent"], "%Y-%m-%d").date()
        hoy = datetime.now(timezone.utc).date()
        dias = (fecha_partido - hoy).days
        hora = (primero.get("strTime") or "")[:5]
        if dias <= 0:
            return f"⚽ ¡Hoy empieza la jornada! Primer partido a las {hora}." if hora else "⚽ ¡Hoy empieza la jornada!"
        if dias == 1:
            return "⏳ Mañana empieza la jornada. Última oportunidad para fichar."
        return f"⏳ Quedan {dias} días para la próxima jornada."
    except Exception:
        return None


def cargar_csv(path, parse_fecha=True):
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if parse_fecha and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", utc=True)
    return df


# ------------------------------------------------------------------
# División en hilo de tweets (máx. 280 caracteres cada uno)
# ------------------------------------------------------------------
def dividir_en_hilo(texto):
    max_len = LIMITE_TWEET - MARGEN_CONTADOR
    bloques = [b for b in texto.split("\n\n") if b.strip() != ""]
    tweets = []
    actual = ""

    def cerrar_actual():
        nonlocal actual
        if actual:
            tweets.append(actual)
            actual = ""

    for bloque in bloques:
        candidato = f"{actual}\n\n{bloque}" if actual else bloque
        if len(candidato) <= max_len:
            actual = candidato
            continue
        cerrar_actual()
        if len(bloque) <= max_len:
            actual = bloque
            continue
        palabras = bloque.split(" ")
        for palabra in palabras:
            candidato = f"{actual} {palabra}".strip()
            if len(candidato) <= max_len:
                actual = candidato
            else:
                cerrar_actual()
                actual = palabra
    cerrar_actual()

    n = len(tweets)
    if n > 1:
        tweets = [f"{t}\n\n({i}/{n})" for i, t in enumerate(tweets, 1)]
    return tweets


def formatear_salida(tweets):
    if len(tweets) == 1:
        return tweets[0]
    partes = []
    for i, t in enumerate(tweets, 1):
        partes.append(f"[[[ TWEET {i}/{len(tweets)} — {len(t)} caracteres ]]]\n{t}")
    return "\n\n".join(partes)


# ------------------------------------------------------------------
# Bancos de contenido fijo (educativo / encuesta), en lenguaje simple
# ------------------------------------------------------------------
BANCO_EDUCATIVO = [
    (
        "🧠 ¿Cómo sabe el radar qué jugador va a subir de precio?\n\n"
        "Mira cómo ha jugado últimamente, si su precio ya está subiendo, "
        "y si esa subida es de verdad o solo un espejismo de un día.\n\n"
        f"{HASHTAGS}"
    ),
    (
        "🧠 A veces un jugador parece bueno pero el radar no lo recomienda.\n\n"
        "Es porque ya falló varias veces antes. Mejor prevenir que fichar a lo loco. 😅\n\n"
        f"{HASHTAGS}"
    ),
    (
        "🧠 Dato curioso: el precio no solo sube por marcar goles.\n\n"
        "Lo que hizo un jugador en los últimos 2-3 días pesa casi tanto como toda la semana.\n\n"
        f"{HASHTAGS}"
    ),
    (
        "🧠 ¿Por qué solo doy 5 jugadores y no 20?\n\n"
        "Porque si te doy demasiados, no sabes por cuál decidirte. "
        "Prefiero darte pocos, pero buenos.\n\n"
        f"{HASHTAGS}"
    ),
]

BANCO_ENCUESTA = [
    (
        "💬 ¿Qué quieres que analice más esta semana?\n\n"
        "🔵 Centrocampistas baratos\n"
        "🔴 Porteros en buena racha\n"
        "🟡 Delanteros que van a bajar\n\n"
        f"{HASHTAGS}"
    ),
    (
        "💬 ¿En quién confías más para fichar?\n\n"
        "🔵 En los datos (como el radar)\n"
        "🔴 En tu ojo de aficionado\n\n"
        "Yo tengo mi favorito, ¡pero quiero saber el tuyo! 👀\n\n"
        f"{HASHTAGS}"
    ),
    (
        "💬 Encuesta rápida:\n\n"
        "🔵 Ficho cuando el jugador YA está subiendo\n"
        "🔴 Espero a que baje un poco antes\n\n"
        f"{HASHTAGS}"
    ),
]


# ------------------------------------------------------------------
# Generadores de cada tipo de post (lenguaje sencillo, sin jerga)
# ------------------------------------------------------------------
def post_oportunidades(ranking, info_jornada):
    top = ranking[ranking["score"] >= 35].head(5)
    if top.empty:
        top = ranking.head(5)
    mejor = top.iloc[0]
    lines = [f"🎯 ¡Hoy el radar encontró {len(top)} jugadores que van a subir de precio!"]
    if info_jornada:
        lines.append(info_jornada)
    lines += [
        "",
        f"El que más nos gusta: {mejor['nickname']}. Ya ha subido un "
        f"{mejor['var_7d']:+.1f}% esta semana. {etiqueta(mejor['score'])}",
        "",
        "Los 5 de hoy:",
    ]
    for i, (_, r) in enumerate(top.iterrows(), 1):
        lines.append(f"{i}. {r['nickname']} — {etiqueta(r['score'])}")
    lines += ["", "¿Fichas a alguno? 👇", "", HASHTAGS]
    return "\n".join(lines)


def post_seguimiento(memoria, fecha_actual):
    ventana = memoria[
        (memoria["fecha"] <= fecha_actual - pd.Timedelta(days=6))
        & (memoria["fecha"] >= fecha_actual - pd.Timedelta(days=12))
        & memoria["rentabilidad_7d"].notna()
    ]
    if ventana.empty:
        return None
    ventana = ventana.sort_values("rentabilidad_7d", ascending=False).drop_duplicates(
        subset="nickname", keep="first"
    )
    mejor = ventana.iloc[0]
    dias = (fecha_actual - mejor["fecha"]).days
    otros = ventana[ventana["nickname"] != mejor["nickname"]].head(3)
    lines = [
        f"📊 Hace {dias} días dijimos que {mejor['nickname']} iba a subir...",
        "",
        f"¡Y subió un {mejor['rentabilidad_7d']:+.1f}%! 🎉",
        "",
    ]
    if not otros.empty:
        lines.append("Otros que también acertamos:")
        for _, r in otros.iterrows():
            lines.append(f"• {r['nickname']} — {r['rentabilidad_7d']:+.1f}%")
        lines.append("")
    lines.append("El radar no acierta siempre, pero cuando acierta, ¡lo borda!")
    lines += ["", HASHTAGS]
    return "\n".join(lines)


def post_resumen_semanal(memoria, fecha_actual):
    semana = memoria[
        (memoria["fecha"] > fecha_actual - pd.Timedelta(days=7))
        & (memoria["fecha"] <= fecha_actual)
    ]
    if semana.empty:
        return None
    con_rent = semana[semana["rentabilidad_7d"].notna()]
    n_jugadores = semana["nickname"].nunique()
    lines = ["📈 Así fue la semana del radar:", "", f"Vigilamos {n_jugadores} jugadores."]
    if not con_rent.empty:
        media = con_rent["rentabilidad_7d"].mean()
        mejor = con_rent.sort_values("rentabilidad_7d", ascending=False).iloc[0]
        lines.append(f"De media, subieron un {media:+.1f}%.")
        lines.append(f"El que más subió: {mejor['nickname']}, con un {mejor['rentabilidad_7d']:+.1f}%. 🚀")
    lines += ["", "¡La semana que viene, más!", "", HASHTAGS]
    return "\n".join(lines)


def post_analisis_posicion(ranking, info_jornada):
    lines = ["🔎 Un jugador top de cada posición hoy:"]
    if info_jornada:
        lines.append(info_jornada)
    lines.append("")
    encontrado = False
    for pid, nombre in POSICIONES.items():
        sub = ranking[ranking["positionId"] == pid]
        if sub.empty:
            continue
        mejor = sub.sort_values("score", ascending=False).iloc[0]
        lines.append(f"{nombre}: {mejor['nickname']}")
        encontrado = True
    if not encontrado:
        return None
    lines += ["", "¡Así no metes todos los huevos en la misma cesta! 🧺", "", HASHTAGS]
    return "\n".join(lines)


def post_educativo(fecha_actual):
    idx = fecha_actual.isocalendar()[1] % len(BANCO_EDUCATIVO)
    return BANCO_EDUCATIVO[idx]


def post_encuesta(fecha_actual):
    idx = fecha_actual.isocalendar()[1] % len(BANCO_ENCUESTA)
    return BANCO_ENCUESTA[idx]


def main():
    ranking = cargar_csv(RANKING_FILE)
    memoria = cargar_csv(MEMORIA_FILE)
    if ranking.empty:
        raise RuntimeError("No hay ranking_actual_v3_3.csv — ejecuta antes motor_diario_v3_3.py")

    fecha_actual = pd.to_datetime(ranking["fecha"].max())
    dia_semana = fecha_actual.weekday()  # 0=lunes ... 6=domingo
    info_jornada = obtener_info_jornada()

    post = None
    origen = ""

    if dia_semana in (0, 3):  # lunes, jueves
        post = post_oportunidades(ranking, info_jornada)
        origen = "oportunidades"
    elif dia_semana == 1:  # martes
        post = post_seguimiento(memoria, fecha_actual)
        origen = "seguimiento"
    elif dia_semana == 2:  # miércoles
        post = post_educativo(fecha_actual)
        origen = "educativo"
    elif dia_semana == 4:  # viernes
        post = post_encuesta(fecha_actual)
        origen = "encuesta"
    elif dia_semana == 5:  # sábado
        post = post_analisis_posicion(ranking, info_jornada)
        origen = "analisis_posicion"
    elif dia_semana == 6:  # domingo
        post = post_resumen_semanal(memoria, fecha_actual)
        origen = "resumen_semanal"

    if post is None:
        post = post_oportunidades(ranking, info_jornada)
        origen = "oportunidades (fallback por falta de histórico)"

    tweets = dividir_en_hilo(post)
    salida = formatear_salida(tweets)

    POST_FILE.write_text(salida, encoding="utf-8")
    print("=" * 70)
    print("POST VARIADO GENERADO")
    print("=" * 70)
    print(f"Día de la semana: {dia_semana} | Tipo: {origen} | Tweets en el hilo: {len(tweets)}")
    print(f"Info de jornada: {info_jornada}")
    print()
    print(salida)


if __name__ == "__main__":
    main()