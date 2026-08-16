import pandas as pd 
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "datos"

HISTORICO_FILE = DATA_DIR / "historico_precios.csv"
JUGADORES_FILE = DATA_DIR / "jugadores_laliga.csv"


# ============================================================
# CONFIGURACIÓN
# ============================================================

DIAS_7 = 7
DIAS_3 = 3
DIAS_1 = 1

# positionId:
# 1 = Portero
# 2 = Defensa
# 3 = Centrocampista
# 4 = Delantero
# 5 = Entrenador

POSICIONES = {
    1: "POR",
    2: "DEF",
    3: "MED",
    4: "DEL",
    5: "ENT",
}


# ============================================================
# CARGA DE DATOS
# ============================================================

print("Cargando datos...")

historico = pd.read_csv(HISTORICO_FILE)
jugadores = pd.read_csv(JUGADORES_FILE)

historico["date"] = pd.to_datetime(
    historico["date"],
    errors="coerce"
)

historico["marketValue"] = pd.to_numeric(
    historico["marketValue"],
    errors="coerce"
)

jugadores["marketValue"] = pd.to_numeric(
    jugadores["marketValue"],
    errors="coerce"
)

jugadores["lastSeasonPoints"] = pd.to_numeric(
    jugadores["lastSeasonPoints"],
    errors="coerce"
)

jugadores["points"] = pd.to_numeric(
    jugadores["points"],
    errors="coerce"
)

jugadores["positionId"] = pd.to_numeric(
    jugadores["positionId"],
    errors="coerce"
)

print(f"Registros históricos: {len(historico)}")
print(f"Jugadores: {len(jugadores)}")

fecha_max = historico["date"].max()

print(f"Fecha más reciente: {fecha_max}")


# ============================================================
# FUNCIÓN PARA OBTENER PRECIO DE HACE N DÍAS
# ============================================================

def precio_historico(grupo, dias):

    fecha_objetivo = fecha_max - pd.Timedelta(days=dias)

    grupo = grupo.sort_values("date")

    anteriores = grupo[grupo["date"] <= fecha_objetivo]

    if anteriores.empty:
        return None

    return anteriores.iloc[-1]["marketValue"]


# ============================================================
# CALCULAR TENDENCIAS
# ============================================================

resultados = []

for _, jugador in jugadores.iterrows():

    player_id = jugador["id"]

    grupo = historico[
        historico["player_id"] == player_id
    ].copy()

    if grupo.empty:
        continue

    grupo = grupo.sort_values("date")

    precio_actual = grupo.iloc[-1]["marketValue"]

    if pd.isna(precio_actual) or precio_actual <= 0:
        continue

    precio_7d = precio_historico(grupo, DIAS_7)
    precio_3d = precio_historico(grupo, DIAS_3)
    precio_1d = precio_historico(grupo, DIAS_1)

    var_7d = None
    var_3d = None
    var_1d = None

    if precio_7d and precio_7d > 0:
        var_7d = (
            (precio_actual - precio_7d)
            / precio_7d
        ) * 100

    if precio_3d and precio_3d > 0:
        var_3d = (
            (precio_actual - precio_3d)
            / precio_3d
        ) * 100

    if precio_1d and precio_1d > 0:
        var_1d = (
            (precio_actual - precio_1d)
            / precio_1d
        ) * 100

    resultados.append({
        "id": player_id,
        "nickname": jugador["nickname"],
        "positionId": jugador["positionId"],
        "precio": precio_actual,
        "lastSeasonPoints": jugador["lastSeasonPoints"],
        "points": jugador["points"],
        "var_7d": var_7d,
        "var_3d": var_3d,
        "var_1d": var_1d,
    })


df = pd.DataFrame(resultados)


# ============================================================
# ELIMINAR ENTRENADORES
# ============================================================

df = df[df["positionId"] != 5].copy()


# ============================================================
# NORMALIZAR DATOS
# ============================================================

df["var_7d"] = df["var_7d"].fillna(0)
df["var_3d"] = df["var_3d"].fillna(0)
df["var_1d"] = df["var_1d"].fillna(0)

df["lastSeasonPoints"] = (
    df["lastSeasonPoints"]
    .fillna(0)
)

df["points"] = (
    df["points"]
    .fillna(0)
)


# ============================================================
# MODELO DE PUNTUACIÓN
# ============================================================

# ------------------------------------------------------------
# 1. SCORE DE RENDIMIENTO
# ------------------------------------------------------------
# Utilizamos los puntos de la temporada anterior.
# Se normaliza por precio para detectar valor fantasy.

df["rendimiento_ratio"] = (
    df["lastSeasonPoints"].fillna(0)
    / (df["precio"].clip(lower=1) / 1_000_000)
)

df["score_rendimiento"] = (
    df["rendimiento_ratio"] * 0.25
).clip(lower=0, upper=40)


# ------------------------------------------------------------
# 2. SCORE DE INVERSIÓN
# ------------------------------------------------------------
# Detecta tendencia positiva de mercado.
#
# 7 días  = 50%
# 3 días  = 30%
# 1 día   = 20%


# ============================================================
# SCORE DE FICHAJE
# ============================================================

# El fichaje debe priorizar:
# 1. Tendencia reciente
# 2. Aceleración de la subida
# 3. Rendimiento histórico
# 4. Precio razonable
#
# El momentum tiene más peso que el precio para evitar
# que jugadores baratos pero estancados aparezcan arriba.


# ------------------------------------------------------------
# 1. MOMENTUM
# ------------------------------------------------------------

df["score_tendencia"] = (
    df["var_7d"] * 0.50
    + df["var_3d"] * 0.30
    + df["var_1d"] * 0.20
)

df["score_tendencia"] = (
    df["score_tendencia"] * 1.5
).clip(lower=0, upper=40)


# ------------------------------------------------------------
# 2. ACELERACIÓN
# ------------------------------------------------------------

df["aceleracion_fichaje"] = (
    df["var_1d"]
    - (df["var_3d"] / 3)
)

df["score_aceleracion"] = 0.0

df.loc[
    (df["var_7d"] > 5) &
    (df["var_3d"] > 2) &
    (df["var_1d"] > 0),
    "score_aceleracion"
] += 5

df.loc[
    (df["var_7d"] > 10) &
    (df["var_3d"] > 4) &
    (df["var_1d"] > 1),
    "score_aceleracion"
] += 5


# ------------------------------------------------------------
# 3. RENDIMIENTO HISTÓRICO
# ------------------------------------------------------------

df["valor_historico"] = (
    df["lastSeasonPoints"].fillna(0)
    / (df["precio"].clip(lower=1) / 1_000_000)
)

df["score_historico"] = (
    df["valor_historico"] / 100 * 15
).clip(lower=0, upper=15)


# ------------------------------------------------------------
# 4. PRECIO
# ------------------------------------------------------------

df["score_precio"] = (
    15 - (df["precio"] / 1_000_000)
).clip(lower=0, upper=15)

df["score_precio_final"] = (
    df["score_precio"] / 15 * 10
)


# ------------------------------------------------------------
# 5. SCORE DE FICHAJE
# ------------------------------------------------------------

df["score_fichaje"] = (
    df["score_tendencia"]
    + df["score_aceleracion"]
    + df["score_historico"]
    + df["score_precio_final"]
)


# ============================================================
# PENALIZACIONES
# ============================================================

df.loc[
    df["var_7d"] < -5,
    "score_fichaje"
] -= 5

df.loc[
    df["var_7d"] < -10,
    "score_fichaje"
] -= 8

df.loc[
    df["var_7d"] < -15,
    "score_fichaje"
] -= 12

df.loc[
    (df["var_7d"] < 0) &
    (df["var_1d"] < 0),
    "score_fichaje"
] -= 5

df["score_fichaje"] = (
    df["score_fichaje"]
    .clip(lower=0, upper=100)
)


# ============================================================
# SCORE DE ESPECULACIÓN
# ============================================================

df["score_especulacion"] = (
    df["var_7d"] * 0.50
    + df["var_3d"] * 0.30
    + df["var_1d"] * 0.20
)


# Aceleración

df["aceleracion"] = (
    df["var_1d"]
    - (df["var_3d"] / 3)
)

df.loc[
    df["aceleracion"] > 1,
    "score_especulacion"
] += 5

df.loc[
    df["aceleracion"] > 2,
    "score_especulacion"
] += 5


# Jugadores baratos con subida fuerte

df.loc[
    (df["precio"] < 5_000_000) &
    (df["var_7d"] > 10),
    "score_especulacion"
] += 8

df.loc[
    (df["precio"] < 10_000_000) &
    (df["var_7d"] > 15),
    "score_especulacion"
] += 5


# Penalización por caída

df.loc[
    df["var_7d"] < 0,
    "score_especulacion"
] -= 10

df.loc[
    (df["var_7d"] < 0) &
    (df["var_1d"] < 0),
    "score_especulacion"
] -= 10

df["score_especulacion"] = (
    df["score_especulacion"]
    .clip(lower=0, upper=100)
)


# ============================================================
# POTENCIAL DE SUBIDA
# ============================================================

df["precio_teorico"] = (
    df["lastSeasonPoints"].fillna(0) * 50_000
)

df["potencial_bruto"] = (
    (
        df["precio_teorico"] - df["precio"]
    )
    / df["precio"].clip(lower=1)
) * 100

df["potencial_bruto"] = (
    df["potencial_bruto"]
    .clip(lower=-100, upper=200)
)

df["potencial_subida"] = (
    (df["potencial_bruto"] + 100)
    / 300 * 100
).clip(lower=0, upper=100)


# Bonus por tendencia positiva

df.loc[
    (df["var_7d"] > 10) &
    (df["var_3d"] > 3) &
    (df["var_1d"] > 0),
    "potencial_subida"
] += 10

df.loc[
    (df["var_7d"] > 20) &
    (df["var_3d"] > 7) &
    (df["var_1d"] > 2),
    "potencial_subida"
] += 10

df["potencial_subida"] = (
    df["potencial_subida"]
    .clip(lower=0, upper=100)
)


# ============================================================
# SCORE GLOBAL
# ============================================================

df["score"] = (
    df["score_fichaje"] * 0.60
    + df["score_especulacion"] * 0.20
    + df["potencial_subida"] * 0.20
).clip(lower=0, upper=100)


# ============================================================
# RESULTADOS
# ============================================================

print()
print("=" * 78)
print("🏆 TOP 20 FICHAJES RECOMENDADOS")
print("=" * 78)

top_fichajes = df.sort_values(
    "score",
    ascending=False
).head(20)

for _, jugador in top_fichajes.iterrows():

    posicion = POSICIONES.get(
        int(jugador["positionId"]),
        "?"
    )

    print(
        f"{jugador['nickname']:<25}"
        f"{posicion:<5}"
        f"{jugador['precio']:>12,.0f} €   "
        f"7d:{jugador['var_7d']:>8.2f}%   "
        f"3d:{jugador['var_3d']:>8.2f}%   "
        f"1d:{jugador['var_1d']:>8.2f}%   "
        f"SCORE:{jugador['score']:>6.1f}"
    )


print()
print("=" * 78)
print("🚀 TOP 20 ESPECULACIONES")
print("=" * 78)

especulacion = df[
    (df["var_7d"] > 5) &
    (df["var_1d"] > 0)
].copy()

especulacion = especulacion.sort_values(
    ["var_7d", "var_1d"],
    ascending=False
).head(20)

for _, jugador in especulacion.iterrows():

    posicion = POSICIONES.get(
        int(jugador["positionId"]),
        "?"
    )

    print(
        f"{jugador['nickname']:<25}"
        f"{posicion:<5}"
        f"{jugador['precio']:>12,.0f} €   "
        f"+{jugador['var_7d']:>7.2f}%   "
        f"1d:{jugador['var_1d']:>7.2f}%"
    )


print()
print("=" * 78)
print("💎 TOP 20 CHOLLOS")
print("=" * 78)

chollos = df[
    (df["precio"] < 5_000_000) &
    (df["lastSeasonPoints"] > 50)
].copy()

chollos["valor"] = (
    chollos["lastSeasonPoints"]
    / (chollos["precio"] / 1_000_000)
)

chollos = chollos.sort_values(
    "valor",
    ascending=False
).head(20)

for _, jugador in chollos.iterrows():

    posicion = POSICIONES.get(
        int(jugador["positionId"]),
        "?"
    )

    print(
        f"{jugador['nickname']:<25}"
        f"{posicion:<5}"
        f"{jugador['precio']:>12,.0f} €   "
        f"{jugador['lastSeasonPoints']:>6.0f} pts   "
        f"Valor:{jugador['valor']:>6.1f}"
    )


print()
print("=" * 78)
print("🔻 TOP 20 POSIBLES VENTAS")
print("=" * 78)

ventas = df.sort_values(
    "var_7d",
    ascending=True
).head(20)

for _, jugador in ventas.iterrows():

    posicion = POSICIONES.get(
        int(jugador["positionId"]),
        "?"
    )

    print(
        f"{jugador['nickname']:<25}"
        f"{posicion:<5}"
        f"{jugador['precio']:>12,.0f} €   "
        f"7d:{jugador['var_7d']:>8.2f}%   "
        f"1d:{jugador['var_1d']:>8.2f}%"
    )


print()
print("=" * 78)
print("✅ ANÁLISIS TERMINADO")
print("=" * 78)

