# ============================================================
# BACKTEST.PY
# Fantasy LaLiga
#
# V3 - MEMORIA ADAPTATIVA BASADA EN FALLOS
#
# PRINCIPAL CAMBIO RESPECTO A V2:
#
# La V2 penalizaba indirectamente a los jugadores que aparecían
# muchas veces en el TOP20 mediante PESO_REPETICION.
#
# En V3:
#
# - APARECER MUCHAS VECES NO ES UN MOTIVO DE PENALIZACIÓN.
# - La frecuencia únicamente determina si existe suficiente
#   muestra histórica para evaluar al jugador.
# - La penalización depende de la evidencia de que las
#   recomendaciones anteriores sobre ese jugador han fallado.
#
# Criterios V3:
#
# 1. Rentabilidad media 7d negativa.
# 2. Porcentaje de acierto bajo.
# 3. Racha de fallos consecutivos.
# 4. Deterioro reciente del rendimiento.
#
# CERO LOOK-AHEAD BIAS:
#
# Para cada fecha:
# - El score de esa fecha NO utiliza rentabilidades futuras.
# - La memoria solo contiene recomendaciones de fechas anteriores.
# - La rentabilidad futura de una recomendación se utiliza
#   exclusivamente para evaluar esa recomendación posteriormente.
#
# El script calcula:
#
# - SCORE BASE
# - SCORE ADAPTATIVO V2
# - SCORE ADAPTATIVO V3
# - Comparación V2 vs V3
# - TOP 5 / TOP 10 / TOP 20
# - Umbrales
# - Correlaciones
# - Simulación de estrategias
# - Jugadores problemáticos
# - Jugadores repetidos
# - Impacto de valores extremos
# - Exportaciones CSV
# ============================================================


import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "datos"

HISTORICO_FILE = DATA_DIR / "historico_precios.csv"
JUGADORES_FILE = DATA_DIR / "jugadores_laliga.csv"

DIAS_7 = 7
DIAS_3 = 3
DIAS_1 = 1

TOPS = [5, 10, 20]

MIN_DIAS_FUTURO = 7

TRIM_PERCENT = 0.05


# ============================================================
# CONFIGURACIÓN MEMORIA ADAPTATIVA
# ============================================================

# Mínimo de recomendaciones anteriores antes de evaluar
# seriamente el comportamiento del jugador.
MIN_APARICIONES_PENALIZACION = 5

# Número máximo de recomendaciones históricas utilizadas.
VENTANA_MEMORIA = 8

# Penalización máxima.
PENALIZACION_MAXIMA = 25.0

# A partir de este porcentaje de acierto consideramos que
# el comportamiento empieza a ser malo.
UMBRAL_ACIERTO_BUENO = 60.0

# Pesos V2
PESO_RACHA_FALLOS_V2 = 1.5
PESO_RENTABILIDAD_V2 = 0.65
PESO_FALLOS_V2 = 0.12
PESO_REPETICION_V2 = 0.35

# V3
#
# IMPORTANTE:
# NO existe peso de repetición.
#
# La aparición adicional de un jugador NO genera penalización.
#
# Los pesos se han diseñado para que la penalización dependa
# principalmente de evidencia de fallo.

PESO_RENTABILIDAD_V3 = 1.10
PESO_FALLOS_V3 = 0.18
PESO_RACHA_FALLOS_V3 = 1.75
PESO_DETERIORO_V3 = 0.45

# Límite individual de los componentes V3.
MAX_RENTABILIDAD_V3 = 10.0
MAX_FALLOS_V3 = 8.0
MAX_RACHA_V3 = 8.0
MAX_DETERIORO_V3 = 7.0

# Solo jugadores que hayan entrado en este TOP se consideran
# recomendaciones históricas.
TOP_MEMORIA = 20


# ============================================================
# POSICIONES
# ============================================================

POSICIONES = {
    1: "POR",
    2: "DEF",
    3: "MED",
    4: "DEL",
    5: "ENT",
}


# ============================================================
# CABECERA
# ============================================================

print()
print("=" * 78)
print("🧪 BACKTEST DEL MODELO DE OPORTUNIDADES - V3")
print("=" * 78)
print()

print("VERSIÓN V3")
print()
print("Cambio principal:")
print("La frecuencia de aparición NO genera penalización.")
print("Solo se penaliza evidencia histórica de fallo.")
print("Look-ahead bias: DESACTIVADO.")
print()


# ============================================================
# CARGA DE DATOS
# ============================================================

print("Cargando datos...")

historico = pd.read_csv(HISTORICO_FILE)
jugadores = pd.read_csv(JUGADORES_FILE)


# ============================================================
# HISTÓRICO
# ============================================================

historico["date"] = pd.to_datetime(
    historico["date"],
    errors="coerce"
)

historico["marketValue"] = pd.to_numeric(
    historico["marketValue"],
    errors="coerce"
)

historico["player_id"] = pd.to_numeric(
    historico["player_id"],
    errors="coerce"
)


# ============================================================
# JUGADORES
# ============================================================

jugadores["id"] = pd.to_numeric(
    jugadores["id"],
    errors="coerce"
)

jugadores["positionId"] = pd.to_numeric(
    jugadores["positionId"],
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


# ============================================================
# LIMPIEZA
# ============================================================

historico = historico.dropna(
    subset=[
        "date",
        "marketValue",
        "player_id"
    ]
).copy()

historico = historico[
    historico["marketValue"] > 0
].copy()

historico = historico.sort_values(
    ["player_id", "date"]
).copy()


print(
    f"Registros históricos: {len(historico):,}"
)

print(
    f"Jugadores: {len(jugadores):,}"
)


fecha_min = historico["date"].min()
fecha_max = historico["date"].max()

print(
    f"Primera fecha:       {fecha_min}"
)

print(
    f"Última fecha:        {fecha_max}"
)

print()


# ============================================================
# EXCLUIR ENTRENADORES
# ============================================================

jugadores_validos = jugadores[
    jugadores["positionId"] != 5
].copy()

ids_historico = set(
    historico["player_id"].unique()
)

jugadores_validos = jugadores_validos[
    jugadores_validos["id"].isin(ids_historico)
].copy()


entrenadores_excluidos = (
    len(jugadores)
    - len(jugadores_validos)
)


validos_ids = set(
    jugadores_validos["id"].dropna()
)


historico = historico[
    historico["player_id"].isin(validos_ids)
].copy()


print(
    f"Jugadores válidos para el backtest: "
    f"{len(jugadores_validos):,}"
)

print(
    f"Entrenadores excluidos: "
    f"{entrenadores_excluidos:,}"
)

print(
    f"Registros históricos tras excluir entrenadores: "
    f"{len(historico):,}"
)

print()


# ============================================================
# DICCIONARIOS
# ============================================================

nombres = dict(
    zip(
        jugadores_validos["id"],
        jugadores_validos["nickname"]
    )
)

posiciones = dict(
    zip(
        jugadores_validos["id"],
        jugadores_validos["positionId"]
    )
)

last_points = dict(
    zip(
        jugadores_validos["id"],
        jugadores_validos["lastSeasonPoints"]
    )
)


# ============================================================
# HISTÓRICO POR JUGADOR
# ============================================================

historicos = {}

for player_id, grupo in historico.groupby(
    "player_id"
):

    grupo = grupo.sort_values(
        "date"
    ).copy()

    grupo = grupo.drop_duplicates(
        subset=["date"],
        keep="last"
    )

    historicos[player_id] = grupo


# ============================================================
# FUNCIONES DE PRECIOS
# ============================================================

def obtener_precio_anterior(
    grupo,
    fecha
):

    anteriores = grupo[
        grupo["date"] <= fecha
    ]

    if anteriores.empty:
        return None

    return anteriores.iloc[-1]["marketValue"]


def obtener_precio_futuro(
    grupo,
    fecha,
    dias
):

    fecha_objetivo = (
        fecha
        + pd.Timedelta(days=dias)
    )

    posteriores = grupo[
        grupo["date"] >= fecha_objetivo
    ]

    if posteriores.empty:
        return None

    return posteriores.iloc[0]["marketValue"]


# ============================================================
# SCORE BASE
# ============================================================

def calcular_score_base(
    precio,
    var_7d,
    var_3d,
    var_1d,
    last_season_points
):

    if pd.isna(last_season_points):
        last_season_points = 0

    precio_millones = max(
        precio / 1_000_000,
        0.000001
    )

    # --------------------------------------------------------
    # RENDIMIENTO
    # --------------------------------------------------------

    rendimiento_ratio = (
        last_season_points
        / precio_millones
    )

    score_rendimiento = np.clip(
        rendimiento_ratio * 0.25,
        0,
        40
    )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    score_tendencia = (
        var_7d * 0.50
        + var_3d * 0.30
        + var_1d * 0.20
    )

    score_tendencia = np.clip(
        score_tendencia * 1.5,
        0,
        40
    )

    # --------------------------------------------------------
    # ACELERACIÓN
    # --------------------------------------------------------

    aceleracion = (
        var_1d
        - (var_3d / 3)
    )

    score_aceleracion = 0

    if (
        var_7d > 5
        and var_3d > 2
        and var_1d > 0
    ):
        score_aceleracion += 5

    if (
        var_7d > 10
        and var_3d > 4
        and var_1d > 1
    ):
        score_aceleracion += 5

    # --------------------------------------------------------
    # HISTÓRICO
    # --------------------------------------------------------

    valor_historico = (
        last_season_points
        / precio_millones
    )

    score_historico = np.clip(
        valor_historico / 100 * 15,
        0,
        15
    )

    # --------------------------------------------------------
    # PRECIO
    # --------------------------------------------------------

    score_precio = np.clip(
        15 - precio_millones,
        0,
        15
    )

    score_precio_final = (
        score_precio / 15 * 10
    )

    # --------------------------------------------------------
    # SCORE FICHAJE
    # --------------------------------------------------------

    score_fichaje = (
        score_tendencia
        + score_aceleracion
        + score_historico
        + score_precio_final
    )

    # --------------------------------------------------------
    # PENALIZACIONES DE DETERIORO
    # --------------------------------------------------------

    penalizacion_deterioro = 0

    if var_7d < -5:
        penalizacion_deterioro += 5

    if var_7d < -10:
        penalizacion_deterioro += 8

    if var_7d < -15:
        penalizacion_deterioro += 12

    if (
        var_7d < 0
        and var_1d < 0
    ):
        penalizacion_deterioro += 5

    score_fichaje -= penalizacion_deterioro

    score_fichaje = np.clip(
        score_fichaje,
        0,
        100
    )

    # --------------------------------------------------------
    # ESPECULACIÓN
    # --------------------------------------------------------

    score_especulacion = (
        var_7d * 0.50
        + var_3d * 0.30
        + var_1d * 0.20
    )

    if aceleracion > 1:
        score_especulacion += 5

    if aceleracion > 2:
        score_especulacion += 5

    if (
        precio < 5_000_000
        and var_7d > 10
    ):
        score_especulacion += 8

    if (
        precio < 10_000_000
        and var_7d > 15
    ):
        score_especulacion += 5

    if var_7d < 0:
        score_especulacion -= 10

    if (
        var_7d < 0
        and var_1d < 0
    ):
        score_especulacion -= 10

    score_especulacion = np.clip(
        score_especulacion,
        0,
        100
    )

    # --------------------------------------------------------
    # POTENCIAL DE SUBIDA
    # --------------------------------------------------------

    precio_teorico = (
        last_season_points * 50_000
    )

    potencial_bruto = (
        (
            precio_teorico
            - precio
        )
        / max(precio, 1)
    ) * 100

    potencial_bruto = np.clip(
        potencial_bruto,
        -100,
        200
    )

    potencial_subida = (
        (potencial_bruto + 100)
        / 300
        * 100
    )

    if (
        var_7d > 10
        and var_3d > 3
        and var_1d > 0
    ):
        potencial_subida += 10

    if (
        var_7d > 20
        and var_3d > 7
        and var_1d > 2
    ):
        potencial_subida += 10

    potencial_subida = np.clip(
        potencial_subida,
        0,
        100
    )

    # --------------------------------------------------------
    # SCORE GLOBAL
    # --------------------------------------------------------

    score = (
        score_fichaje * 0.60
        + score_especulacion * 0.20
        + potencial_subida * 0.20
    )

    return float(
        np.clip(score, 0, 100)
    )


# ============================================================
# FECHAS
# ============================================================

todas_las_fechas = sorted(
    historico[
        "date"
    ]
    .dt
    .normalize()
    .unique()
)

fecha_inicio = (
    pd.Timestamp(fecha_min)
    .normalize()
    + pd.Timedelta(days=DIAS_7)
)

fecha_fin = (
    pd.Timestamp(fecha_max)
    .normalize()
    - pd.Timedelta(
        days=MIN_DIAS_FUTURO
    )
)

fechas_test = [
    pd.Timestamp(f)
    for f in todas_las_fechas
    if (
        pd.Timestamp(f) >= fecha_inicio
        and
        pd.Timestamp(f) <= fecha_fin
    )
]


print(
    f"Fechas disponibles para backtest: "
    f"{len(fechas_test)}"
)

print(
    f"Periodo probado: "
    f"{fecha_inicio.date()} → "
    f"{fecha_fin.date()}"
)

print()


# ============================================================
# PRIMERA PASADA
#
# Calculamos:
# - score_base
# - rentabilidades futuras
#
# Las rentabilidades futuras NO se utilizan todavía para
# decidir el score.
# ============================================================

print("=" * 78)
print("📊 PRIMERA PASADA - SCORE BASE")
print("=" * 78)
print()


resultados_base = []

total_fechas = len(fechas_test)


for numero_fecha, fecha in enumerate(
    fechas_test,
    start=1
):

    if numero_fecha % 10 == 0:
        print(
            f"Procesando fecha "
            f"{numero_fecha}/{total_fechas} "
            f"({fecha.date()})"
        )

    candidatos = []

    for player_id, grupo in historicos.items():

        actuales = grupo[
            grupo["date"] <= fecha
        ]

        if actuales.empty:
            continue

        actual = actuales.iloc[-1]

        precio_actual = (
            actual["marketValue"]
        )

        if (
            pd.isna(precio_actual)
            or precio_actual <= 0
        ):
            continue

        # ----------------------------------------------------
        # PRECIOS PASADOS
        # ----------------------------------------------------

        precio_7d = obtener_precio_anterior(
            grupo,
            fecha - pd.Timedelta(days=7)
        )

        precio_3d = obtener_precio_anterior(
            grupo,
            fecha - pd.Timedelta(days=3)
        )

        precio_1d = obtener_precio_anterior(
            grupo,
            fecha - pd.Timedelta(days=1)
        )

        if (
            precio_7d is None
            or precio_3d is None
            or precio_1d is None
        ):
            continue

        if (
            precio_7d <= 0
            or precio_3d <= 0
            or precio_1d <= 0
        ):
            continue

        # ----------------------------------------------------
        # VARIACIONES
        # ----------------------------------------------------

        var_7d = (
            (
                precio_actual
                - precio_7d
            )
            / precio_7d
        ) * 100

        var_3d = (
            (
                precio_actual
                - precio_3d
            )
            / precio_3d
        ) * 100

        var_1d = (
            (
                precio_actual
                - precio_1d
            )
            / precio_1d
        ) * 100

        # ----------------------------------------------------
        # PUNTOS
        # ----------------------------------------------------

        last_season_points = (
            last_points.get(
                player_id,
                0
            )
        )

        if pd.isna(last_season_points):
            last_season_points = 0

        # ----------------------------------------------------
        # SCORE BASE
        # ----------------------------------------------------

        score_base = calcular_score_base(
            precio_actual,
            var_7d,
            var_3d,
            var_1d,
            last_season_points
        )

        # ----------------------------------------------------
        # FUTURO
        #
        # Se utiliza exclusivamente para medir posteriormente
        # si esta recomendación funcionó.
        # ----------------------------------------------------

        precio_1f = obtener_precio_futuro(
            grupo,
            fecha,
            1
        )

        precio_3f = obtener_precio_futuro(
            grupo,
            fecha,
            3
        )

        precio_7f = obtener_precio_futuro(
            grupo,
            fecha,
            7
        )

        if (
            precio_1f is None
            or precio_3f is None
            or precio_7f is None
        ):
            continue

        # ----------------------------------------------------
        # RENTABILIDADES FUTURAS
        # ----------------------------------------------------

        rentabilidad_1d = (
            (
                precio_1f
                - precio_actual
            )
            / precio_actual
        ) * 100

        rentabilidad_3d = (
            (
                precio_3f
                - precio_actual
            )
            / precio_actual
        ) * 100

        rentabilidad_7d = (
            (
                precio_7f
                - precio_actual
            )
            / precio_actual
        ) * 100

        candidatos.append({

            "fecha": fecha,

            "player_id": player_id,

            "nickname": nombres.get(
                player_id,
                str(player_id)
            ),

            "positionId": posiciones.get(
                player_id,
                0
            ),

            "precio": precio_actual,

            "var_7d": var_7d,
            "var_3d": var_3d,
            "var_1d": var_1d,

            "score_base": score_base,

            "rentabilidad_1d": (
                rentabilidad_1d
            ),

            "rentabilidad_3d": (
                rentabilidad_3d
            ),

            "rentabilidad_7d": (
                rentabilidad_7d
            ),
        })

    if candidatos:
        resultados_base.extend(
            candidatos
        )


# ============================================================
# DATAFRAME BASE
# ============================================================

bt_base = pd.DataFrame(
    resultados_base
)

if bt_base.empty:

    print()
    print(
        "❌ No hay datos suficientes "
        "para realizar el backtest."
    )

    raise SystemExit


print()
print("=" * 78)
print("📊 PRIMERA PASADA COMPLETADA")
print("=" * 78)

print(
    f"Observaciones: "
    f"{len(bt_base):,}"
)

print(
    f"Fechas analizadas: "
    f"{bt_base['fecha'].nunique():,}"
)

print()


# ============================================================
# FUNCIONES DE MEMORIA
# ============================================================


def resultado_memoria_vacio():

    return {
        "penalizacion": 0.0,
        "apariciones": 0,
        "rentabilidad_media_7d": 0.0,
        "acierto_7d": 100.0,
        "fallos_consecutivos": 0,
        "deterioro_reciente": 0.0,
    }


# ============================================================
# PENALIZACIÓN ADAPTATIVA V2
#
# Se conserva para poder comparar directamente V2 vs V3.
# ============================================================

def calcular_penalizacion_v2(
    player_id,
    fecha,
    historial
):

    if historial.empty:
        return resultado_memoria_vacio()

    jugador = historial[
        historial["player_id"] == player_id
    ].copy()

    jugador = jugador[
        jugador["fecha"] < fecha
    ].copy()

    if jugador.empty:
        return resultado_memoria_vacio()

    jugador = jugador.sort_values(
        "fecha"
    )

    if len(jugador) > VENTANA_MEMORIA:

        jugador = jugador.tail(
            VENTANA_MEMORIA
        )

    apariciones = len(jugador)

    rentabilidad_media = jugador[
        "rentabilidad_7d"
    ].mean()

    acierto = (
        jugador[
            "rentabilidad_7d"
        ] > 0
    ).mean() * 100

    if (
        apariciones
        < MIN_APARICIONES_PENALIZACION
    ):

        return {
            "penalizacion": 0.0,
            "apariciones": apariciones,
            "rentabilidad_media_7d": float(
                rentabilidad_media
            ),
            "acierto_7d": float(
                acierto
            ),
            "fallos_consecutivos": 0,
            "deterioro_reciente": 0.0,
        }

    # --------------------------------------------------------
    # RACHA
    # --------------------------------------------------------

    fallos_consecutivos = 0

    for resultado in reversed(
        jugador[
            "rentabilidad_7d"
        ].tolist()
    ):

        if resultado <= 0:
            fallos_consecutivos += 1
        else:
            break

    # --------------------------------------------------------
    # DETERIORO
    # --------------------------------------------------------

    if len(jugador) >= 6:

        mitad = len(jugador) // 2

        antigua = jugador[
            "rentabilidad_7d"
        ].iloc[:mitad].mean()

        reciente = jugador[
            "rentabilidad_7d"
        ].iloc[mitad:].mean()

        deterioro_reciente = (
            antigua - reciente
        )

    else:

        deterioro_reciente = 0.0

    # --------------------------------------------------------
    # COMPONENTE RENTABILIDAD
    # --------------------------------------------------------

    componente_rentabilidad = 0.0

    if rentabilidad_media < 0:

        componente_rentabilidad = min(
            abs(rentabilidad_media)
            * PESO_RENTABILIDAD_V2,
            10
        )

    # --------------------------------------------------------
    # COMPONENTE FALLOS
    # --------------------------------------------------------

    porcentaje_fallos = (
        100 - acierto
    )

    componente_fallos = 0.0

    if acierto < UMBRAL_ACIERTO_BUENO:

        componente_fallos = min(
            porcentaje_fallos
            * PESO_FALLOS_V2,
            10
        )

    # --------------------------------------------------------
    # COMPONENTE REPETICIÓN
    #
    # ESTE ES EL COMPONENTE PROBLEMÁTICO DE V2.
    # --------------------------------------------------------

    componente_repeticion = min(
        max(
            apariciones
            - MIN_APARICIONES_PENALIZACION
            + 1,
            0
        )
        * PESO_REPETICION_V2,
        5
    )

    # --------------------------------------------------------
    # COMPONENTE RACHA
    # --------------------------------------------------------

    componente_racha = min(
        fallos_consecutivos
        * PESO_RACHA_FALLOS_V2,
        8
    )

    # --------------------------------------------------------
    # COMPONENTE DETERIORO
    # --------------------------------------------------------

    componente_deterioro = 0.0

    if deterioro_reciente > 2:

        componente_deterioro = min(
            deterioro_reciente * 0.25,
            5
        )

    # --------------------------------------------------------
    # TOTAL V2
    # --------------------------------------------------------

    penalizacion = (
        componente_rentabilidad
        + componente_fallos
        + componente_repeticion
        + componente_racha
        + componente_deterioro
    )

    penalizacion = np.clip(
        penalizacion,
        0,
        PENALIZACION_MAXIMA
    )

    return {

        "penalizacion": float(
            penalizacion
        ),

        "apariciones": int(
            apariciones
        ),

        "rentabilidad_media_7d": float(
            rentabilidad_media
        ),

        "acierto_7d": float(
            acierto
        ),

        "fallos_consecutivos": int(
            fallos_consecutivos
        ),

        "deterioro_reciente": float(
            deterioro_reciente
        ),
    }


# ============================================================
# PENALIZACIÓN ADAPTATIVA V3
#
# PRINCIPIO:
#
# APARECER MUCHO ≠ SER MALO
#
# La frecuencia no suma ni un solo punto de penalización.
#
# Un jugador que aparece 20 veces y tiene un 70% de acierto
# puede seguir siendo una buena recomendación.
#
# Un jugador que aparece 5 veces y falla sistemáticamente
# sí debe ser penalizado.
# ============================================================

def calcular_penalizacion_v3(
    player_id,
    fecha,
    historial
):

    if historial.empty:
        return resultado_memoria_vacio()

    jugador = historial[
        historial["player_id"] == player_id
    ].copy()

    # ========================================================
    # CERO LOOK-AHEAD BIAS
    #
    # Solo recomendaciones estrictamente anteriores.
    # ========================================================

    jugador = jugador[
        jugador["fecha"] < fecha
    ].copy()

    if jugador.empty:
        return resultado_memoria_vacio()

    jugador = jugador.sort_values(
        "fecha"
    )

    # ========================================================
    # VENTANA DE MEMORIA
    # ========================================================

    if len(jugador) > VENTANA_MEMORIA:

        jugador = jugador.tail(
            VENTANA_MEMORIA
        )

    apariciones = len(jugador)

    # ========================================================
    # ESTADÍSTICAS HISTÓRICAS
    # ========================================================

    rentabilidad_media = jugador[
        "rentabilidad_7d"
    ].mean()

    acierto = (
        jugador[
            "rentabilidad_7d"
        ] > 0
    ).mean() * 100

    # ========================================================
    # MUESTRA INSUFICIENTE
    #
    # Importante:
    #
    # La falta de muestra NO genera penalización.
    #
    # Simplemente todavía no confiamos en la memoria.
    # ========================================================

    if (
        apariciones
        < MIN_APARICIONES_PENALIZACION
    ):

        return {
            "penalizacion": 0.0,
            "apariciones": apariciones,
            "rentabilidad_media_7d": float(
                rentabilidad_media
            ),
            "acierto_7d": float(
                acierto
            ),
            "fallos_consecutivos": 0,
            "deterioro_reciente": 0.0,
        }

    # ========================================================
    # RACHA DE FALLOS
    # ========================================================

    fallos_consecutivos = 0

    for resultado in reversed(
        jugador[
            "rentabilidad_7d"
        ].tolist()
    ):

        if resultado <= 0:
            fallos_consecutivos += 1
        else:
            break

    # ========================================================
    # DETERIORO RECIENTE
    #
    # Comparamos la primera mitad de la memoria con la segunda.
    #
    # Positivo = el jugador está empeorando.
    # ========================================================

    if len(jugador) >= 6:

        mitad = len(jugador) // 2

        antigua = jugador[
            "rentabilidad_7d"
        ].iloc[:mitad].mean()

        reciente = jugador[
            "rentabilidad_7d"
        ].iloc[mitad:].mean()

        deterioro_reciente = (
            antigua - reciente
        )

    else:

        deterioro_reciente = 0.0

    # ========================================================
    # COMPONENTE 1
    #
    # RENTABILIDAD NEGATIVA
    #
    # Si las recomendaciones sobre el jugador generan pérdidas
    # medias, aumenta la penalización.
    # ========================================================

    componente_rentabilidad = 0.0

    if rentabilidad_media < 0:

        componente_rentabilidad = min(
            abs(rentabilidad_media)
            * PESO_RENTABILIDAD_V3,
            MAX_RENTABILIDAD_V3
        )

    # ========================================================
    # COMPONENTE 2
    #
    # PORCENTAJE DE FALLOS
    #
    # Solo se aplica cuando el acierto está por debajo del 60%.
    # ========================================================

    componente_fallos = 0.0

    if acierto < UMBRAL_ACIERTO_BUENO:

        porcentaje_fallos = (
            100 - acierto
        )

        exceso_fallos = max(
            porcentaje_fallos - 40,
            0
        )

        componente_fallos = min(
            exceso_fallos
            * PESO_FALLOS_V3,
            MAX_FALLOS_V3
        )

    # ========================================================
    # COMPONENTE 3
    #
    # RACHA DE FALLOS
    #
    # Penaliza especialmente cuando el problema es reciente
    # y se mantiene consecutivamente.
    # ========================================================

    componente_racha = min(
        fallos_consecutivos
        * PESO_RACHA_FALLOS_V3,
        MAX_RACHA_V3
    )

    # ========================================================
    # COMPONENTE 4
    #
    # DETERIORO RECIENTE
    # ========================================================

    componente_deterioro = 0.0

    if deterioro_reciente > 2:

        componente_deterioro = min(
            deterioro_reciente
            * PESO_DETERIORO_V3,
            MAX_DETERIORO_V3
        )

    # ========================================================
    # PENALIZACIÓN V3
    #
    # NO HAY COMPONENTE DE REPETICIÓN.
    # ========================================================

    penalizacion = (
        componente_rentabilidad
        + componente_fallos
        + componente_racha
        + componente_deterioro
    )

    penalizacion = np.clip(
        penalizacion,
        0,
        PENALIZACION_MAXIMA
    )

    return {

        "penalizacion": float(
            penalizacion
        ),

        "apariciones": int(
            apariciones
        ),

        "rentabilidad_media_7d": float(
            rentabilidad_media
        ),

        "acierto_7d": float(
            acierto
        ),

        "fallos_consecutivos": int(
            fallos_consecutivos
        ),

        "deterioro_reciente": float(
            deterioro_reciente
        ),
    }


# ============================================================
# SEGUNDA PASADA
#
# Calculamos V2 y V3 simultáneamente.
#
# Para cada fecha:
#
# 1. Se recupera únicamente el historial anterior.
# 2. Se calcula V2.
# 3. Se calcula V3.
# 4. Se genera el ranking.
# 5. SOLO DESPUÉS se añade la fecha actual a memoria.
#
# De esta forma la rentabilidad futura de la fecha actual
# jamás puede influir en la recomendación de esa misma fecha.
# ============================================================

print("=" * 78)
print("🧠 APLICANDO MEMORIA ADAPTATIVA V2 Y V3")
print("=" * 78)
print()

memoria_v2 = []
memoria_v3 = []

resultados_v2 = []
resultados_v3 = []


for numero_fecha, fecha in enumerate(
    sorted(bt_base["fecha"].unique()),
    start=1
):

    fecha = pd.Timestamp(fecha)

    datos_fecha = bt_base[
        bt_base["fecha"] == fecha
    ].copy()

    # ========================================================
    # HISTORIAL V2
    # ========================================================

    if memoria_v2:

        historial_v2 = pd.concat(
            memoria_v2,
            ignore_index=True
        )

    else:

        historial_v2 = pd.DataFrame()

    # ========================================================
    # HISTORIAL V3
    # ========================================================

    if memoria_v3:

        historial_v3 = pd.concat(
            memoria_v3,
            ignore_index=True
        )

    else:

        historial_v3 = pd.DataFrame()

    # ========================================================
    # CALCULAR V2 Y V3
    # ========================================================

    filas_v2 = []
    filas_v3 = []

    for _, fila_original in datos_fecha.iterrows():

        fila_v2 = fila_original.copy()
        fila_v3 = fila_original.copy()

        # ----------------------------------------------------
        # V2
        # ----------------------------------------------------

        info_v2 = calcular_penalizacion_v2(
            fila_original["player_id"],
            fecha,
            historial_v2
        )

        fila_v2[
            "penalizacion_adaptativa"
        ] = info_v2[
            "penalizacion"
        ]

        fila_v2[
            "memoria_apariciones"
        ] = info_v2[
            "apariciones"
        ]

        fila_v2[
            "memoria_rent_7d"
        ] = info_v2[
            "rentabilidad_media_7d"
        ]

        fila_v2[
            "memoria_acierto_7d"
        ] = info_v2[
            "acierto_7d"
        ]

        fila_v2[
            "memoria_fallos_consecutivos"
        ] = info_v2[
            "fallos_consecutivos"
        ]

        fila_v2[
            "memoria_deterioro"
        ] = info_v2[
            "deterioro_reciente"
        ]

        fila_v2[
            "score"
        ] = np.clip(
            fila_v2["score_base"]
            - fila_v2[
                "penalizacion_adaptativa"
            ],
            0,
            100
        )

        # ----------------------------------------------------
        # V3
        # ----------------------------------------------------

        info_v3 = calcular_penalizacion_v3(
            fila_original["player_id"],
            fecha,
            historial_v3
        )

        fila_v3[
            "penalizacion_adaptativa"
        ] = info_v3[
            "penalizacion"
        ]

        fila_v3[
            "memoria_apariciones"
        ] = info_v3[
            "apariciones"
        ]

        fila_v3[
            "memoria_rent_7d"
        ] = info_v3[
            "rentabilidad_media_7d"
        ]

        fila_v3[
            "memoria_acierto_7d"
        ] = info_v3[
            "acierto_7d"
        ]

        fila_v3[
            "memoria_fallos_consecutivos"
        ] = info_v3[
            "fallos_consecutivos"
        ]

        fila_v3[
            "memoria_deterioro"
        ] = info_v3[
            "deterioro_reciente"
        ]

        fila_v3[
            "score"
        ] = np.clip(
            fila_v3["score_base"]
            - fila_v3[
                "penalizacion_adaptativa"
            ],
            0,
            100
        )

        filas_v2.append(
            fila_v2
        )

        filas_v3.append(
            fila_v3
        )

    fecha_v2 = pd.DataFrame(
        filas_v2
    )

    fecha_v3 = pd.DataFrame(
        filas_v3
    )

    resultados_v2.append(
        fecha_v2
    )

    resultados_v3.append(
        fecha_v3
    )

    # ========================================================
    # MEMORIA V2
    #
    # La V2 utilizaba TOP20 según score BASE.
    #
    # Se mantiene así para reproducir exactamente su lógica.
    # ========================================================

    top_memoria_v2 = (
        datos_fecha
        .sort_values(
            "score_base",
            ascending=False
        )
        .head(TOP_MEMORIA)
        .copy()
    )

    if not top_memoria_v2.empty:

        memoria_v2.append(
            top_memoria_v2[
                [
                    "fecha",
                    "player_id",
                    "nickname",
                    "rentabilidad_7d",
                    "score_base",
                ]
            ]
        )

    # ========================================================
    # MEMORIA V3
    #
    # AQUÍ ESTÁ UNA DE LAS DIFERENCIAS IMPORTANTES.
    #
    # La memoria representa las recomendaciones reales V3.
    #
    # Por tanto se guarda el TOP20 según SCORE V3.
    #
    # La rentabilidad de esta fecha solo será visible para
    # fechas posteriores.
    # ========================================================

    top_memoria_v3 = (
        fecha_v3
        .sort_values(
            "score",
            ascending=False
        )
        .head(TOP_MEMORIA)
        .copy()
    )

    if not top_memoria_v3.empty:

        memoria_v3.append(
            top_memoria_v3[
                [
                    "fecha",
                    "player_id",
                    "nickname",
                    "rentabilidad_7d",
                    "score_base",
                    "score",
                ]
            ]
        )


# ============================================================
# DATAFRAMES FINALES
# ============================================================

bt_v2 = pd.concat(
    resultados_v2,
    ignore_index=True
)

bt_v3 = pd.concat(
    resultados_v3,
    ignore_index=True
)


# ============================================================
# EL DATAFRAME PRINCIPAL DEL SCRIPT ES V3
# ============================================================

bt = bt_v3.copy()


print()
print(
    f"Observaciones V2: "
    f"{len(bt_v2):,}"
)

print(
    f"Observaciones V3: "
    f"{len(bt_v3):,}"
)

print()


# ============================================================
# FUNCIÓN TOP
# ============================================================

def obtener_top_por_fecha(
    dataframe,
    n,
    columna_score="score"
):

    grupos = []

    for fecha, grupo in dataframe.groupby(
        "fecha"
    ):

        top = (
            grupo
            .sort_values(
                columna_score,
                ascending=False
            )
            .head(n)
        )

        if not top.empty:
            grupos.append(top)

    if not grupos:
        return pd.DataFrame()

    return pd.concat(
        grupos,
        ignore_index=True
    )


# ============================================================
# ESTADÍSTICAS
# ============================================================

def estadisticas_rentabilidad(
    dataframe,
    columna
):

    if dataframe.empty:
        return None

    serie = dataframe[
        columna
    ].dropna()

    if serie.empty:
        return None

    media = serie.mean()
    mediana = serie.median()

    acierto = (
        (serie > 0).mean()
        * 100
    )

    peor = serie.min()
    mejor = serie.max()

    if len(serie) >= 20:

        serie_ordenada = np.sort(
            serie.values
        )

        recorte = int(
            len(serie_ordenada)
            * TRIM_PERCENT
        )

        if (
            recorte > 0
            and
            len(serie_ordenada)
            > recorte * 2
        ):

            serie_recortada = (
                serie_ordenada[
                    recorte:
                    len(serie_ordenada)
                    - recorte
                ]
            )

            media_recortada = (
                serie_recortada.mean()
            )

        else:

            media_recortada = media

    else:

        media_recortada = media

    return {
        "media": media,
        "mediana": mediana,
        "media_recortada": media_recortada,
        "acierto": acierto,
        "peor": peor,
        "mejor": mejor,
        "n": len(serie),
    }


# ============================================================
# EFICACIA SCORE V3
# ============================================================

print()
print("=" * 78)
print("🏆 EFICACIA DEL SCORE ADAPTATIVO V3")
print("=" * 78)


resumen_top = []


for n in TOPS:

    print()
    print(f"TOP {n}")

    top = obtener_top_por_fecha(
        bt_v3,
        n,
        "score"
    )

    for dias, columna in [
        (1, "rentabilidad_1d"),
        (3, "rentabilidad_3d"),
        (7, "rentabilidad_7d"),
    ]:

        stats = estadisticas_rentabilidad(
            top,
            columna
        )

        if stats is None:
            continue

        print(
            f"  +{dias} días → "
            f"Media: {stats['media']:+.3f}%   "
            f"Mediana: {stats['mediana']:+.3f}%   "
            f"Sin extremos: "
            f"{stats['media_recortada']:+.3f}%   "
            f"Acierto: {stats['acierto']:.1f}%   "
            f"Peor: {stats['peor']:+.2f}%   "
            f"Mejor: {stats['mejor']:+.2f}%"
        )

        resumen_top.append({

            "top": n,

            "dias": dias,

            "media": stats["media"],

            "mediana": stats["mediana"],

            "media_sin_extremos":
                stats["media_recortada"],

            "acierto":
                stats["acierto"],

            "peor":
                stats["peor"],

            "mejor":
                stats["mejor"],

            "observaciones":
                stats["n"],
        })


# ============================================================
# SCORE BASE VS V3
# ============================================================

print()
print("=" * 78)
print("🧠 SCORE BASE VS SCORE ADAPTATIVO V3")
print("=" * 78)


comparacion_scores = []


for n in TOPS:

    top_base = obtener_top_por_fecha(
        bt_v3,
        n,
        "score_base"
    )

    top_v3 = obtener_top_por_fecha(
        bt_v3,
        n,
        "score"
    )

    print()
    print(
        f"TOP {n}"
    )

    for dias, columna in [
        (1, "rentabilidad_1d"),
        (3, "rentabilidad_3d"),
        (7, "rentabilidad_7d"),
    ]:

        stats_base = (
            estadisticas_rentabilidad(
                top_base,
                columna
            )
        )

        stats_v3 = (
            estadisticas_rentabilidad(
                top_v3,
                columna
            )
        )

        if (
            stats_base is None
            or
            stats_v3 is None
        ):
            continue

        diferencia = (
            stats_v3["media"]
            - stats_base["media"]
        )

        print(
            f"+{dias} días → "
            f"Base: "
            f"{stats_base['media']:+.3f}% | "
            f"V3: "
            f"{stats_v3['media']:+.3f}% | "
            f"Diferencia: "
            f"{diferencia:+.3f} pp"
        )

        comparacion_scores.append({

            "top": n,

            "dias": dias,

            "base":
                stats_base["media"],

            "v3":
                stats_v3["media"],

            "diferencia":
                diferencia,
        })


# ============================================================
# COMPARACIÓN DIRECTA V2 VS V3
# ============================================================

print()
print("=" * 78)
print("⚔️ COMPARACIÓN DIRECTA V2 VS V3")
print("=" * 78)


comparacion_v2_v3 = []


for n in TOPS:

    top_v2 = obtener_top_por_fecha(
        bt_v2,
        n,
        "score"
    )

    top_v3 = obtener_top_por_fecha(
        bt_v3,
        n,
        "score"
    )

    print()
    print(
        f"TOP {n}"
    )

    for dias, columna in [
        (1, "rentabilidad_1d"),
        (3, "rentabilidad_3d"),
        (7, "rentabilidad_7d"),
    ]:

        stats_v2 = estadisticas_rentabilidad(
            top_v2,
            columna
        )

        stats_v3 = estadisticas_rentabilidad(
            top_v3,
            columna
        )

        if (
            stats_v2 is None
            or
            stats_v3 is None
        ):
            continue

        diferencia = (
            stats_v3["media"]
            - stats_v2["media"]
        )

        diferencia_acierto = (
            stats_v3["acierto"]
            - stats_v2["acierto"]
        )

        print(
            f"+{dias} días → "
            f"V2: {stats_v2['media']:+.3f}% | "
            f"V3: {stats_v3['media']:+.3f}% | "
            f"Δ: {diferencia:+.3f} pp | "
            f"Acierto V2: "
            f"{stats_v2['acierto']:.1f}% | "
            f"Acierto V3: "
            f"{stats_v3['acierto']:.1f}%"
        )

        comparacion_v2_v3.append({

            "top": n,

            "dias": dias,

            "v2_media":
                stats_v2["media"],

            "v3_media":
                stats_v3["media"],

            "diferencia_media":
                diferencia,

            "v2_mediana":
                stats_v2["mediana"],

            "v3_mediana":
                stats_v3["mediana"],

            "v2_media_sin_extremos":
                stats_v2["media_recortada"],

            "v3_media_sin_extremos":
                stats_v3["media_recortada"],

            "v2_acierto":
                stats_v2["acierto"],

            "v3_acierto":
                stats_v3["acierto"],

            "diferencia_acierto":
                diferencia_acierto,

            "v2_peor":
                stats_v2["peor"],

            "v3_peor":
                stats_v3["peor"],

            "v2_mejor":
                stats_v2["mejor"],

            "v3_mejor":
                stats_v3["mejor"],

            "v2_observaciones":
                stats_v2["n"],

            "v3_observaciones":
                stats_v3["n"],
        })


# ============================================================
# SCORE V2 VS V3
# ============================================================

print()
print("=" * 78)
print("📐 DIFERENCIA DE PENALIZACIONES V2 VS V3")
print("=" * 78)


comparacion_penalizaciones = []


media_pen_v2 = (
    bt_v2[
        "penalizacion_adaptativa"
    ].mean()
)

media_pen_v3 = (
    bt_v3[
        "penalizacion_adaptativa"
    ].mean()
)


print(
    f"Penalización media V2: "
    f"{media_pen_v2:.3f}"
)

print(
    f"Penalización media V3: "
    f"{media_pen_v3:.3f}"
)

print(
    f"Diferencia: "
    f"{media_pen_v3 - media_pen_v2:+.3f}"
)


comparacion_penalizaciones.append({

    "metrica":
        "penalizacion_media",

    "v2":
        media_pen_v2,

    "v3":
        media_pen_v3,

    "diferencia":
        media_pen_v3 - media_pen_v2,
})


# ============================================================
# JUGADORES DONDE V2 PENALIZA POR REPETICIÓN
#
# Esta sección sirve para detectar precisamente el problema
# que queremos solucionar.
# ============================================================

print()
print("=" * 78)
print("🔎 CASOS DONDE V2 PENALIZA MÁS QUE V3")
print("=" * 78)


bt_comparacion_pen = bt_v2[
    [
        "fecha",
        "player_id",
        "nickname",
        "penalizacion_adaptativa",
        "memoria_apariciones",
        "memoria_rent_7d",
        "memoria_acierto_7d",
        "memoria_fallos_consecutivos",
        "memoria_deterioro",
    ]
].copy()


bt_comparacion_pen = (
    bt_comparacion_pen
    .rename(
        columns={
            "penalizacion_adaptativa":
                "penalizacion_v2"
        }
    )
)


bt_comparacion_pen["penalizacion_v3"] = (
    bt_v3[
        "penalizacion_adaptativa"
    ].values
)


bt_comparacion_pen[
    "diferencia_v2_menos_v3"
] = (
    bt_comparacion_pen[
        "penalizacion_v2"
    ]
    -
    bt_comparacion_pen[
        "penalizacion_v3"
    ]
)


casos_repeticion = (
    bt_comparacion_pen
    .sort_values(
        "diferencia_v2_menos_v3",
        ascending=False
    )
    .head(20)
)


for _, fila in casos_repeticion.iterrows():

    print(
        f"{str(fila['nickname']):<25} "
        f"apariciones:{int(fila['memoria_apariciones']):>2} | "
        f"V2:-{fila['penalizacion_v2']:.2f} | "
        f"V3:-{fila['penalizacion_v3']:.2f} | "
        f"acierto:{fila['memoria_acierto_7d']:.1f}% | "
        f"rent:{fila['memoria_rent_7d']:+.2f}%"
    )


# ============================================================
# SCORE VS MERCADO
# ============================================================

print()
print("=" * 78)
print("📈 SCORE ADAPTATIVO V3 VS MERCADO")
print("=" * 78)


resumen_mercado = []


for dias, columna in [
    (1, "rentabilidad_1d"),
    (3, "rentabilidad_3d"),
    (7, "rentabilidad_7d"),
]:

    mercado = bt_v3[
        columna
    ].mean()

    top20 = obtener_top_por_fecha(
        bt_v3,
        20,
        "score"
    )

    stats = estadisticas_rentabilidad(
        top20,
        columna
    )

    if stats is None:
        continue

    ventaja = (
        stats["media"]
        - mercado
    )

    print(
        f"+{dias} días → "
        f"Mercado: {mercado:+.3f}% | "
        f"TOP20: {stats['media']:+.3f}% | "
        f"Ventaja: {ventaja:+.3f}%"
    )

    resumen_mercado.append({

        "dias": dias,

        "mercado": mercado,

        "top20": stats["media"],

        "ventaja": ventaja,
    })


# ============================================================
# EFICACIA SEGÚN SCORE V3
# ============================================================

print()
print("=" * 78)
print("🎯 EFICACIA SEGÚN SCORE FINAL V3")
print("=" * 78)


bt_v3["grupo_score"] = pd.cut(
    bt_v3["score"],
    bins=[
        -1,
        20,
        30,
        40,
        50,
        60,
        70,
        80,
        90,
        100,
    ],
    labels=[
        "<20",
        "20-30",
        "30-40",
        "40-50",
        "50-60",
        "60-70",
        "70-80",
        "80-90",
        "90-100",
    ]
)


resumen_score = (
    bt_v3
    .groupby(
        "grupo_score",
        observed=False
    )
    .agg(
        jugadores=(
            "player_id",
            "count"
        ),

        rent_1d=(
            "rentabilidad_1d",
            "mean"
        ),

        rent_3d=(
            "rentabilidad_3d",
            "mean"
        ),

        rent_7d=(
            "rentabilidad_7d",
            "mean"
        ),
    )
)


for indice, fila in (
    resumen_score.iterrows()
):

    print(
        f"SCORE {str(indice):<8} "
        f"N={int(fila['jugadores']):>5}   "
        f"1d:{fila['rent_1d']:+.3f}%   "
        f"3d:{fila['rent_3d']:+.3f}%   "
        f"7d:{fila['rent_7d']:+.3f}%"
    )


# ============================================================
# UMBRALES
# ============================================================

print()
print("=" * 78)
print("🚦 UMBRAL DE COMPRA SEGÚN SCORE ADAPTATIVO V3")
print("=" * 78)


umbrales = []


for minimo in [
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
]:

    seleccion = bt_v3[
        bt_v3["score"] >= minimo
    ].copy()

    if seleccion.empty:
        continue

    fila = {

        "score_minimo": minimo,

        "observaciones": len(
            seleccion
        ),

        "rent_1d": seleccion[
            "rentabilidad_1d"
        ].mean(),

        "rent_3d": seleccion[
            "rentabilidad_3d"
        ].mean(),

        "rent_7d": seleccion[
            "rentabilidad_7d"
        ].mean(),

        "acierto_1d": (
            seleccion[
                "rentabilidad_1d"
            ] > 0
        ).mean() * 100,

        "acierto_3d": (
            seleccion[
                "rentabilidad_3d"
            ] > 0
        ).mean() * 100,

        "acierto_7d": (
            seleccion[
                "rentabilidad_7d"
            ] > 0
        ).mean() * 100,
    }

    umbrales.append(
        fila
    )

    print(
        f"SCORE >= {minimo:<2} | "
        f"N={len(seleccion):>5} | "
        f"1d:{fila['rent_1d']:+.3f}% | "
        f"3d:{fila['rent_3d']:+.3f}% | "
        f"7d:{fila['rent_7d']:+.3f}% | "
        f"Acierto 7d:"
        f"{fila['acierto_7d']:.1f}%"
    )


# ============================================================
# RECOMENDACIÓN DEL UMBRAL
# ============================================================

print()
print("=" * 78)
print("🧠 RECOMENDACIÓN DEL MODELO V3")
print("=" * 78)


if umbrales:

    df_umbrales = pd.DataFrame(
        umbrales
    )

    candidatos_umbrales = (
        df_umbrales[
            df_umbrales[
                "observaciones"
            ] >= 30
        ]
        .sort_values(
            "rent_7d",
            ascending=False
        )
    )

    if not candidatos_umbrales.empty:

        mejor = (
            candidatos_umbrales
            .iloc[0]
        )

        print()
        print(
            f"⭐ Mejor umbral histórico: "
            f"SCORE >= "
            f"{int(mejor['score_minimo'])}"
        )

        print(
            f"   Rentabilidad +1d: "
            f"{mejor['rent_1d']:+.3f}%"
        )

        print(
            f"   Rentabilidad +3d: "
            f"{mejor['rent_3d']:+.3f}%"
        )

        print(
            f"   Rentabilidad +7d: "
            f"{mejor['rent_7d']:+.3f}%"
        )

        print(
            f"   Acierto +7d: "
            f"{mejor['acierto_7d']:.1f}%"
        )

        print(
            f"   Observaciones: "
            f"{int(mejor['observaciones'])}"
        )

    else:

        print(
            "No hay suficientes observaciones "
            "para recomendar un umbral."
        )


# ============================================================
# JUGADORES PROBLEMÁTICOS V3
# ============================================================

print()
print("=" * 78)
print("🚨 JUGADORES PROBLEMÁTICOS - MEMORIA V3")
print("=" * 78)


top20_final = obtener_top_por_fecha(
    bt_v3,
    20,
    "score"
)


problematicos = []


if not top20_final.empty:

    for player_id, grupo in (
        top20_final
        .groupby("player_id")
    ):

        grupo = grupo.sort_values(
            "fecha"
        )

        apariciones = len(grupo)

        if (
            apariciones
            < MIN_APARICIONES_PENALIZACION
        ):
            continue

        rent_7d = grupo[
            "rentabilidad_7d"
        ].mean()

        acierto_7d = (
            grupo[
                "rentabilidad_7d"
            ] > 0
        ).mean() * 100

        penalizacion_media = (
            grupo[
                "penalizacion_adaptativa"
            ].mean()
        )

        ultima_penalizacion = (
            grupo[
                "penalizacion_adaptativa"
            ].iloc[-1]
        )

        fallos = 0

        for resultado in reversed(
            grupo[
                "rentabilidad_7d"
            ].tolist()
        ):

            if resultado <= 0:
                fallos += 1
            else:
                break

        if (
            rent_7d < -2
            or
            acierto_7d < 50
            or
            ultima_penalizacion >= 8
        ):

            problematicos.append({

                "player_id":
                    player_id,

                "nickname":
                    nombres.get(
                        player_id,
                        str(player_id)
                    ),

                "apariciones":
                    apariciones,

                "rentabilidad_7d_media":
                    rent_7d,

                "acierto_7d":
                    acierto_7d,

                "fallos_consecutivos":
                    fallos,

                "penalizacion_media":
                    penalizacion_media,

                "ultima_penalizacion":
                    ultima_penalizacion,
            })


df_problematicos = pd.DataFrame(
    problematicos
)


if df_problematicos.empty:

    print()
    print(
        "No se han detectado jugadores "
        "problemáticos."
    )

else:

    df_problematicos = (
        df_problematicos
        .sort_values(
            [
                "ultima_penalizacion",
                "rentabilidad_7d_media"
            ],
            ascending=[
                False,
                True
            ]
        )
    )

    print()
    print(
        "Jugadores detectados:"
    )
    print()

    for _, fila in (
        df_problematicos.iterrows()
    ):

        print(
            f"{str(fila['nickname']):<25} "
            f"{int(fila['apariciones']):>3} "
            f"apariciones | "
            f"7d:{fila['rentabilidad_7d_media']:+.2f}% | "
            f"Acierto:{fila['acierto_7d']:.1f}% | "
            f"Fallos:{int(fila['fallos_consecutivos'])} | "
            f"Penalización:"
            f"-{fila['ultima_penalizacion']:.2f}"
        )


# ============================================================
# JUGADORES MÁS REPETIDOS
# ============================================================

print()
print("=" * 78)
print("🔥 JUGADORES QUE MÁS VECES APARECEN ENTRE LOS TOP")
print("=" * 78)


if not top20_final.empty:

    frecuencia = (
        top20_final
        .groupby("nickname")
        .agg(

            apariciones=(
                "nickname",
                "count"
            ),

            rentabilidad_1d=(
                "rentabilidad_1d",
                "mean"
            ),

            rentabilidad_3d=(
                "rentabilidad_3d",
                "mean"
            ),

            rentabilidad_7d=(
                "rentabilidad_7d",
                "mean"
            ),
        )
        .sort_values(
            "apariciones",
            ascending=False
        )
        .head(20)
    )

    for nombre, fila in (
        frecuencia.iterrows()
    ):

        print(
            f"{str(nombre):<25} "
            f"{int(fila['apariciones']):>4} veces   "
            f"1d:{fila['rentabilidad_1d']:+.2f}%   "
            f"3d:{fila['rentabilidad_3d']:+.2f}%   "
            f"7d:{fila['rentabilidad_7d']:+.2f}%"
        )


# ============================================================
# REPETIDOS CON MAL RESULTADO
# ============================================================

print()
print("=" * 78)
print("⚠️ JUGADORES REPETIDOS QUE FALLAN")
print("=" * 78)


if not top20_final.empty:

    frecuencia_fallos = (
        top20_final
        .groupby("nickname")
        .agg(

            apariciones=(
                "nickname",
                "count"
            ),

            rentabilidad_7d=(
                "rentabilidad_7d",
                "mean"
            ),

            acierto_7d=(
                "rentabilidad_7d",
                lambda x:
                (
                    x > 0
                ).mean() * 100
            ),
        )
    )

    frecuencia_fallos = (
        frecuencia_fallos[
            frecuencia_fallos[
                "apariciones"
            ] >= 5
        ]
        .sort_values(
            "rentabilidad_7d"
        )
        .head(10)
    )

    for nombre, fila in (
        frecuencia_fallos.iterrows()
    ):

        print(
            f"{str(nombre):<25} "
            f"{int(fila['apariciones']):>4} veces | "
            f"7d:{fila['rentabilidad_7d']:+.2f}% | "
            f"Acierto:"
            f"{fila['acierto_7d']:.1f}%"
        )


# ============================================================
# CORRELACIÓN V3
# ============================================================

print()
print("=" * 78)
print("🔬 CORRELACIÓN SCORE V3 → RENTABILIDAD")
print("=" * 78)


correlaciones = []


for dias, columna in [
    (1, "rentabilidad_1d"),
    (3, "rentabilidad_3d"),
    (7, "rentabilidad_7d"),
]:

    correlacion = (
        bt_v3[
            [
                "score",
                columna
            ]
        ]
        .corr()
        .iloc[0, 1]
    )

    print(
        f"+{dias} días → "
        f"correlación: "
        f"{correlacion:+.4f}"
    )

    correlaciones.append({

        "dias": dias,

        "correlacion":
            correlacion,
    })


# ============================================================
# CORRELACIÓN V2 VS V3
# ============================================================

print()
print("=" * 78)
print("🔬 CORRELACIÓN V2 VS V3")
print("=" * 78)


correlaciones_v2_v3 = []


for dias, columna in [
    (1, "rentabilidad_1d"),
    (3, "rentabilidad_3d"),
    (7, "rentabilidad_7d"),
]:

    corr_v2 = (
        bt_v2[
            [
                "score",
                columna
            ]
        ]
        .corr()
        .iloc[0, 1]
    )

    corr_v3 = (
        bt_v3[
            [
                "score",
                columna
            ]
        ]
        .corr()
        .iloc[0, 1]
    )

    print(
        f"+{dias} días → "
        f"V2:{corr_v2:+.4f} | "
        f"V3:{corr_v3:+.4f} | "
        f"Δ:{corr_v3 - corr_v2:+.4f}"
    )

    correlaciones_v2_v3.append({

        "dias":
            dias,

        "correlacion_v2":
            corr_v2,

        "correlacion_v3":
            corr_v3,

        "diferencia":
            corr_v3 - corr_v2,
    })


# ============================================================
# SIMULACIÓN ESTRATEGIA V3
# ============================================================

print()
print("=" * 78)
print("💰 SIMULACIÓN DE ESTRATEGIA ADAPTATIVA V3")
print("=" * 78)


print(
    "Simulación teórica: cada día se seleccionan "
    "los TOP 5, TOP 10 y TOP 20."
)

print(
    "La rentabilidad diaria de cada estrategia "
    "es la media de los jugadores seleccionados."
)


estrategias = []


for n in TOPS:

    top = obtener_top_por_fecha(
        bt_v3,
        n,
        "score"
    )

    if top.empty:
        continue

    diaria = (
        top
        .groupby("fecha")[
            "rentabilidad_1d"
        ]
        .mean()
        .sort_index()
    )

    if diaria.empty:
        continue

    capital = 100.0

    for rentabilidad in diaria:

        capital *= (
            1
            + rentabilidad / 100
        )

    rentabilidad_acumulada = (
        capital - 100
    )

    peor_dia = diaria.min()
    mejor_dia = diaria.max()

    dias_ganadores = (
        diaria > 0
    ).mean() * 100

    print()
    print(
        f"TOP {n}:"
    )

    print(
        f"   Capital inicial: 100.00"
    )

    print(
        f"   Capital final:   "
        f"{capital:.2f}"
    )

    print(
        f"   Rentabilidad acumulada: "
        f"{rentabilidad_acumulada:+.2f}%"
    )

    print(
        f"   Días positivos: "
        f"{dias_ganadores:.1f}%"
    )

    print(
        f"   Mejor día: "
        f"{mejor_dia:+.2f}%"
    )

    print(
        f"   Peor día: "
        f"{peor_dia:+.2f}%"
    )

    estrategias.append({

        "top": n,

        "capital_inicial": 100,

        "capital_final":
            capital,

        "rentabilidad_acumulada":
            rentabilidad_acumulada,

        "dias_positivos":
            dias_ganadores,

        "mejor_dia":
            mejor_dia,

        "peor_dia":
            peor_dia,
    })


# ============================================================
# SIMULACIÓN V2 VS V3
# ============================================================

print()
print("=" * 78)
print("💰 ESTRATEGIA V2 VS V3")
print("=" * 78)


estrategias_v2_v3 = []


for n in TOPS:

    top_v2 = obtener_top_por_fecha(
        bt_v2,
        n,
        "score"
    )

    top_v3 = obtener_top_por_fecha(
        bt_v3,
        n,
        "score"
    )

    diaria_v2 = (
        top_v2
        .groupby("fecha")[
            "rentabilidad_1d"
        ]
        .mean()
        .sort_index()
    )

    diaria_v3 = (
        top_v3
        .groupby("fecha")[
            "rentabilidad_1d"
        ]
        .mean()
        .sort_index()
    )

    capital_v2 = 100.0
    capital_v3 = 100.0

    for rentabilidad in diaria_v2:

        capital_v2 *= (
            1
            + rentabilidad / 100
        )

    for rentabilidad in diaria_v3:

        capital_v3 *= (
            1
            + rentabilidad / 100
        )

    rent_v2 = (
        capital_v2 - 100
    )

    rent_v3 = (
        capital_v3 - 100
    )

    print()
    print(
        f"TOP {n} → "
        f"V2: {rent_v2:+.2f}% | "
        f"V3: {rent_v3:+.2f}% | "
        f"Δ: {rent_v3 - rent_v2:+.2f} pp"
    )

    estrategias_v2_v3.append({

        "top": n,

        "v2_capital_final":
            capital_v2,

        "v3_capital_final":
            capital_v3,

        "v2_rentabilidad":
            rent_v2,

        "v3_rentabilidad":
            rent_v3,

        "diferencia":
            rent_v3 - rent_v2,
    })


# ============================================================
# IMPACTO VALORES EXTREMOS
# ============================================================

print()
print("=" * 78)
print("🧹 IMPACTO DE VALORES EXTREMOS")
print("=" * 78)


top20 = obtener_top_por_fecha(
    bt_v3,
    20,
    "score"
)


for dias, columna in [
    (1, "rentabilidad_1d"),
    (3, "rentabilidad_3d"),
    (7, "rentabilidad_7d"),
]:

    serie = top20[
        columna
    ].dropna()

    if serie.empty:
        continue

    media_normal = serie.mean()

    q05 = serie.quantile(0.05)
    q95 = serie.quantile(0.95)

    serie_filtrada = serie[
        (serie >= q05)
        &
        (serie <= q95)
    ]

    media_filtrada = (
        serie_filtrada.mean()
    )

    print(
        f"+{dias} días → "
        f"Normal: "
        f"{media_normal:+.3f}% | "
        f"Sin 5% extremos: "
        f"{media_filtrada:+.3f}% | "
        f"Impacto: "
        f"{media_normal - media_filtrada:+.3f} pp"
    )


# ============================================================
# EXPORTACIONES
# ============================================================

print()
print("=" * 78)
print("💾 GUARDANDO RESULTADOS V3")
print("=" * 78)


# ============================================================
# EXPORTACIÓN PRINCIPAL
# ============================================================

salida_bt = (
    DATA_DIR
    / "backtest_resultados.csv"
)

bt_v3.to_csv(
    salida_bt,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# RESULTADOS V3 ESPECÍFICOS
# ============================================================

salida_bt_v3 = (
    DATA_DIR
    / "backtest_v3_resultados.csv"
)

bt_v3.to_csv(
    salida_bt_v3,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# RESULTADOS V2
# ============================================================

salida_bt_v2 = (
    DATA_DIR
    / "backtest_v2_resultados.csv"
)

bt_v2.to_csv(
    salida_bt_v2,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# TOP
# ============================================================

salida_top = (
    DATA_DIR
    / "backtest_resumen_top.csv"
)

pd.DataFrame(
    resumen_top
).to_csv(
    salida_top,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# MERCADO
# ============================================================

salida_mercado = (
    DATA_DIR
    / "backtest_mercado.csv"
)

pd.DataFrame(
    resumen_mercado
).to_csv(
    salida_mercado,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# UMBRALES
# ============================================================

salida_umbrales = (
    DATA_DIR
    / "backtest_umbrales_score.csv"
)

pd.DataFrame(
    umbrales
).to_csv(
    salida_umbrales,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# ESTRATEGIAS
# ============================================================

salida_estrategias = (
    DATA_DIR
    / "backtest_estrategias.csv"
)

pd.DataFrame(
    estrategias
).to_csv(
    salida_estrategias,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# PROBLEMÁTICOS
# ============================================================

salida_problematicos = (
    DATA_DIR
    / "backtest_jugadores_problematicos_v3.csv"
)

df_problematicos.to_csv(
    salida_problematicos,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# CORRELACIONES
# ============================================================

salida_correlaciones = (
    DATA_DIR
    / "backtest_correlaciones.csv"
)

pd.DataFrame(
    correlaciones
).to_csv(
    salida_correlaciones,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# BASE VS V3
# ============================================================

salida_comparacion = (
    DATA_DIR
    / "backtest_base_vs_adaptativo.csv"
)

pd.DataFrame(
    comparacion_scores
).to_csv(
    salida_comparacion,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# NUEVAS EXPORTACIONES V3
# ============================================================

salida_v2_v3 = (
    DATA_DIR
    / "backtest_v2_vs_v3.csv"
)

pd.DataFrame(
    comparacion_v2_v3
).to_csv(
    salida_v2_v3,
    index=False,
    encoding="utf-8-sig"
)


salida_penalizaciones = (
    DATA_DIR
    / "backtest_penalizaciones_v2_vs_v3.csv"
)

pd.DataFrame(
    comparacion_penalizaciones
).to_csv(
    salida_penalizaciones,
    index=False,
    encoding="utf-8-sig"
)


salida_casos_repeticion = (
    DATA_DIR
    / "backtest_casos_repeticion_v2_v3.csv"
)

casos_repeticion.to_csv(
    salida_casos_repeticion,
    index=False,
    encoding="utf-8-sig"
)


salida_correlaciones_v2_v3 = (
    DATA_DIR
    / "backtest_correlaciones_v2_vs_v3.csv"
)

pd.DataFrame(
    correlaciones_v2_v3
).to_csv(
    salida_correlaciones_v2_v3,
    index=False,
    encoding="utf-8-sig"
)


salida_estrategias_v2_v3 = (
    DATA_DIR
    / "backtest_estrategias_v2_vs_v3.csv"
)

pd.DataFrame(
    estrategias_v2_v3
).to_csv(
    salida_estrategias_v2_v3,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# EXPORTAR UMBRALES V3 CON NOMBRE EXPLÍCITO
# ============================================================

salida_umbrales_v3 = (
    DATA_DIR
    / "backtest_v3_umbrales_score.csv"
)

pd.DataFrame(
    umbrales
).to_csv(
    salida_umbrales_v3,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# EXPORTAR TOP V3
# ============================================================

salida_top_v3 = (
    DATA_DIR
    / "backtest_v3_resumen_top.csv"
)

pd.DataFrame(
    resumen_top
).to_csv(
    salida_top_v3,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# FINAL
# ============================================================

print()

print(
    salida_bt
)

print(
    salida_bt_v3
)

print(
    salida_bt_v2
)

print(
    salida_top
)

print(
    salida_mercado
)

print(
    salida_umbrales
)

print(
    salida_estrategias
)

print(
    salida_problematicos
)

print(
    salida_correlaciones
)

print(
    salida_comparacion
)

print(
    salida_v2_v3
)

print(
    salida_penalizaciones
)

print(
    salida_casos_repeticion
)

print(
    salida_correlaciones_v2_v3
)

print(
    salida_estrategias_v2_v3
)

print(
    salida_umbrales_v3
)

print(
    salida_top_v3
)

print()

print("=" * 78)
print("✅ BACKTEST ADAPTATIVO V3 COMPLETADO")
print("=" * 78)
print()
print("IMPORTANTE:")
print("La V3 NO penaliza por número de apariciones.")
print("La frecuencia solo determina si existe muestra suficiente.")
print("La memoria solo utiliza recomendaciones de fechas anteriores.")
print("Las rentabilidades futuras nunca deciden el score de su propia fecha.")
print()