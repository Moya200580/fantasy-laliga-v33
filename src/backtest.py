# ============================================================
# BACKTEST.PY
# Fantasy LaLiga
#
# V2 - PENALIZACIÓN ADAPTATIVA
#
# Características:
# - Excluye entrenadores
# - Score base
# - Penalización por deterioro
# - Memoria histórica de jugadores problemáticos
# - Penalización adaptativa V2
# - Sin look-ahead bias
# - Las penalizaciones solo utilizan información disponible
#   antes de cada fecha del backtest
# - Análisis TOP 5 / TOP 10 / TOP 20
# - Umbrales de score
# - Correlaciones
# - Simulación de estrategia
# - Exportación de jugadores problemáticos
# - Exportación de memoria adaptativa
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
# CONFIGURACIÓN PENALIZACIÓN ADAPTATIVA V2
# ============================================================

# Número mínimo de recomendaciones anteriores antes
# de empezar a penalizar seriamente.
MIN_APARICIONES_PENALIZACION = 5

# Número máximo de recomendaciones históricas utilizadas
# para calcular el comportamiento reciente.
VENTANA_MEMORIA = 8

# Penalización máxima.
PENALIZACION_MAXIMA = 25.0

# Umbral de rentabilidad 7d considerado deterioro.
UMBRAL_RENTABILIDAD_NEGATIVA = 0.0

# A partir de este porcentaje de acierto se considera
# que el jugador está funcionando razonablemente bien.
UMBRAL_ACIERTO_BUENO = 60.0

# Peso de los fallos consecutivos.
PESO_RACHA_FALLOS = 1.5

# Peso de la rentabilidad negativa.
PESO_RENTABILIDAD = 0.65

# Peso del porcentaje de fallos.
PESO_FALLOS = 0.12

# Peso de la frecuencia de aparición.
PESO_REPETICION = 0.35

# La memoria adaptativa solo utiliza jugadores que hayan
# aparecido dentro de este TOP histórico.
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
print("🧪 BACKTEST DEL MODELO DE OPORTUNIDADES - ADAPTATIVO V2")
print("=" * 78)
print()


# ============================================================
# CARGA DE DATOS
# ============================================================

print("Cargando datos...")

historico = pd.read_csv(HISTORICO_FILE)
jugadores = pd.read_csv(JUGADORES_FILE)


# ------------------------------------------------------------
# HISTÓRICO
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# JUGADORES
# ------------------------------------------------------------

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


entrenadores_excluidos = len(jugadores) - len(
    jugadores_validos
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
# Calculamos el score BASE y las rentabilidades futuras.
#
# IMPORTANTE:
# En esta fase todavía NO aplicamos memoria adaptativa.
# ============================================================

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
# PENALIZACIÓN ADAPTATIVA V2
# ============================================================

def calcular_penalizacion_adaptativa(
    player_id,
    fecha,
    historial
):

    if historial.empty:
        return {
            "penalizacion": 0.0,
            "apariciones": 0,
            "rentabilidad_media_7d": 0.0,
            "acierto_7d": 100.0,
            "fallos_consecutivos": 0,
            "deterioro_reciente": 0.0,
        }

    jugador = historial[
        historial["player_id"] == player_id
    ].copy()

    jugador = jugador[
        jugador["fecha"] < fecha
    ].copy()

    if jugador.empty:
        return {
            "penalizacion": 0.0,
            "apariciones": 0,
            "rentabilidad_media_7d": 0.0,
            "acierto_7d": 100.0,
            "fallos_consecutivos": 0,
            "deterioro_reciente": 0.0,
        }

    # --------------------------------------------------------
    # SOLO RECOMENDACIONES ANTERIORES
    #
    # El historial que entra aquí ya está limitado al TOP20
    # de fechas anteriores.
    # --------------------------------------------------------

    jugador = jugador.sort_values(
        "fecha"
    )

    if len(jugador) > VENTANA_MEMORIA:

        jugador = jugador.tail(
            VENTANA_MEMORIA
        )

    apariciones = len(jugador)

    if (
        apariciones
        < MIN_APARICIONES_PENALIZACION
    ):
        return {
            "penalizacion": 0.0,
            "apariciones": apariciones,
            "rentabilidad_media_7d": jugador[
                "rentabilidad_7d"
            ].mean(),
            "acierto_7d": (
                jugador[
                    "rentabilidad_7d"
                ] > 0
            ).mean() * 100,
            "fallos_consecutivos": 0,
            "deterioro_reciente": 0.0,
        }

    # --------------------------------------------------------
    # RENTABILIDAD MEDIA
    # --------------------------------------------------------

    rentabilidad_media = jugador[
        "rentabilidad_7d"
    ].mean()

    # --------------------------------------------------------
    # PORCENTAJE DE ACIERTO
    # --------------------------------------------------------

    acierto = (
        jugador[
            "rentabilidad_7d"
        ] > 0
    ).mean() * 100

    # --------------------------------------------------------
    # RACHA DE FALLOS
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
    # DETERIORO RECIENTE
    #
    # Comparamos la primera mitad de la memoria
    # con la segunda mitad.
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
    # COMPONENTE 1
    # RENTABILIDAD NEGATIVA
    # --------------------------------------------------------

    componente_rentabilidad = 0.0

    if rentabilidad_media < 0:

        componente_rentabilidad = min(
            abs(rentabilidad_media)
            * PESO_RENTABILIDAD,
            10
        )

    # --------------------------------------------------------
    # COMPONENTE 2
    # PORCENTAJE DE FALLOS
    # --------------------------------------------------------

    porcentaje_fallos = (
        100 - acierto
    )

    componente_fallos = 0.0

    if acierto < UMBRAL_ACIERTO_BUENO:

        componente_fallos = min(
            porcentaje_fallos
            * PESO_FALLOS,
            10
        )

    # --------------------------------------------------------
    # COMPONENTE 3
    # REPETICIÓN
    # --------------------------------------------------------

    componente_repeticion = min(
        max(
            apariciones
            - MIN_APARICIONES_PENALIZACION
            + 1,
            0
        )
        * PESO_REPETICION,
        5
    )

    # --------------------------------------------------------
    # COMPONENTE 4
    # RACHA DE FALLOS
    # --------------------------------------------------------

    componente_racha = min(
        fallos_consecutivos
        * PESO_RACHA_FALLOS,
        8
    )

    # --------------------------------------------------------
    # COMPONENTE 5
    # DETERIORO RECIENTE
    # --------------------------------------------------------

    componente_deterioro = 0.0

    if deterioro_reciente > 2:

        componente_deterioro = min(
            deterioro_reciente * 0.25,
            5
        )

    # --------------------------------------------------------
    # PENALIZACIÓN TOTAL
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
# SEGUNDA PASADA
#
# Construimos el TOP20 histórico fecha a fecha.
#
# MUY IMPORTANTE:
# Solo se utilizan recomendaciones anteriores.
# ============================================================

print("=" * 78)
print("🧠 APLICANDO MEMORIA ADAPTATIVA V2")
print("=" * 78)
print()


memoria_recomendaciones = []

resultados_finales = []


for fecha in sorted(
    bt_base["fecha"].unique()
):

    fecha = pd.Timestamp(fecha)

    datos_fecha = bt_base[
        bt_base["fecha"] == fecha
    ].copy()

    # --------------------------------------------------------
    # HISTORIAL PREVIO
    # --------------------------------------------------------

    if memoria_recomendaciones:

        historial_previo = pd.concat(
            memoria_recomendaciones,
            ignore_index=True
        )

    else:

        historial_previo = pd.DataFrame()

    # --------------------------------------------------------
    # CALCULAR PENALIZACIÓN
    # --------------------------------------------------------

    filas_fecha = []

    for _, fila in datos_fecha.iterrows():

        info = calcular_penalizacion_adaptativa(
            fila["player_id"],
            fecha,
            historial_previo
        )

        fila = fila.copy()

        fila[
            "penalizacion_adaptativa"
        ] = info["penalizacion"]

        fila[
            "memoria_apariciones"
        ] = info["apariciones"]

        fila[
            "memoria_rent_7d"
        ] = info[
            "rentabilidad_media_7d"
        ]

        fila[
            "memoria_acierto_7d"
        ] = info["acierto_7d"]

        fila[
            "memoria_fallos_consecutivos"
        ] = info[
            "fallos_consecutivos"
        ]

        fila[
            "memoria_deterioro"
        ] = info[
            "deterioro_reciente"
        ]

        # ----------------------------------------------------
        # SCORE FINAL
        # ----------------------------------------------------

        fila[
            "score"
        ] = np.clip(
            fila["score_base"]
            - fila[
                "penalizacion_adaptativa"
            ],
            0,
            100
        )

        filas_fecha.append(fila)

    fecha_final = pd.DataFrame(
        filas_fecha
    )

    resultados_finales.append(
        fecha_final
    )

    # --------------------------------------------------------
    # CREAR MEMORIA PARA FUTURAS FECHAS
    #
    # La memoria utiliza únicamente el TOP20 por score BASE.
    # Sus rentabilidades futuras ya están disponibles en el
    # backtest histórico, pero pertenecen a esta fecha y solo
    # serán utilizables por fechas posteriores.
    # --------------------------------------------------------

    top_memoria = (
        datos_fecha
        .sort_values(
            "score_base",
            ascending=False
        )
        .head(TOP_MEMORIA)
        .copy()
    )

    if not top_memoria.empty:

        memoria_recomendaciones.append(
            top_memoria[
                [
                    "fecha",
                    "player_id",
                    "nickname",
                    "rentabilidad_7d",
                    "score_base",
                ]
            ]
        )


# ============================================================
# DATAFRAME FINAL
# ============================================================

bt = pd.concat(
    resultados_finales,
    ignore_index=True
)


print(
    f"Observaciones finales: "
    f"{len(bt):,}"
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
# EFICACIA DEL SCORE FINAL
# ============================================================

print()
print("=" * 78)
print("🏆 EFICACIA DEL SCORE ADAPTATIVO V2")
print("=" * 78)


resumen_top = []


for n in TOPS:

    print()
    print(f"TOP {n}")

    top = obtener_top_por_fecha(
        bt,
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
# SCORE BASE VS SCORE ADAPTATIVO
# ============================================================

print()
print("=" * 78)
print("🧠 SCORE BASE VS SCORE ADAPTATIVO")
print("=" * 78)


comparacion_scores = []


for n in TOPS:

    top_base = obtener_top_por_fecha(
        bt,
        n,
        "score_base"
    )

    top_adaptativo = obtener_top_por_fecha(
        bt,
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

        stats_adaptativo = (
            estadisticas_rentabilidad(
                top_adaptativo,
                columna
            )
        )

        if (
            stats_base is None
            or
            stats_adaptativo is None
        ):
            continue

        diferencia = (
            stats_adaptativo["media"]
            - stats_base["media"]
        )

        print(
            f"+{dias} días → "
            f"Base: "
            f"{stats_base['media']:+.3f}% | "
            f"Adaptativo: "
            f"{stats_adaptativo['media']:+.3f}% | "
            f"Diferencia: "
            f"{diferencia:+.3f} pp"
        )

        comparacion_scores.append({

            "top": n,

            "dias": dias,

            "base": stats_base[
                "media"
            ],

            "adaptativo":
                stats_adaptativo[
                    "media"
                ],

            "diferencia":
                diferencia,
        })


# ============================================================
# SCORE VS MERCADO
# ============================================================

print()
print("=" * 78)
print("📈 SCORE ADAPTATIVO VS MERCADO")
print("=" * 78)


resumen_mercado = []


for dias, columna in [
    (1, "rentabilidad_1d"),
    (3, "rentabilidad_3d"),
    (7, "rentabilidad_7d"),
]:

    mercado = bt[
        columna
    ].mean()

    top20 = obtener_top_por_fecha(
        bt,
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
# EFICACIA SEGÚN SCORE
# ============================================================

print()
print("=" * 78)
print("🎯 EFICACIA SEGÚN SCORE FINAL")
print("=" * 78)


bt["grupo_score"] = pd.cut(
    bt["score"],
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
    bt
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
print("🚦 UMBRAL DE COMPRA SEGÚN SCORE ADAPTATIVO")
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

    seleccion = bt[
        bt["score"] >= minimo
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

    umbrales.append(fila)

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
print("🧠 RECOMENDACIÓN DEL MODELO")
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
# JUGADORES PROBLEMÁTICOS V2
# ============================================================

print()
print("=" * 78)
print("🚨 JUGADORES PROBLEMÁTICOS - MEMORIA ADAPTATIVA V2")
print("=" * 78)


top20_final = obtener_top_por_fecha(
    bt,
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

        # Racha de fallos
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

        # Solo consideramos problemáticos
        # aquellos con comportamiento realmente malo.
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
# CORRELACIÓN
# ============================================================

print()
print("=" * 78)
print("🔬 CORRELACIÓN SCORE ADAPTATIVO → RENTABILIDAD")
print("=" * 78)


correlaciones = []


for dias, columna in [
    (1, "rentabilidad_1d"),
    (3, "rentabilidad_3d"),
    (7, "rentabilidad_7d"),
]:

    correlacion = (
        bt[
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
# SIMULACIÓN ESTRATEGIA
# ============================================================

print()
print("=" * 78)
print("💰 SIMULACIÓN DE ESTRATEGIA ADAPTATIVA")
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
        bt,
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
# IMPACTO VALORES EXTREMOS
# ============================================================

print()
print("=" * 78)
print("🧹 IMPACTO DE VALORES EXTREMOS")
print("=" * 78)


top20 = obtener_top_por_fecha(
    bt,
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
print("💾 GUARDANDO RESULTADOS")
print("=" * 78)


salida_bt = (
    DATA_DIR
    / "backtest_resultados.csv"
)

bt.to_csv(
    salida_bt,
    index=False,
    encoding="utf-8-sig"
)


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


salida_problematicos = (
    DATA_DIR
    / "backtest_jugadores_problematicos_v2.csv"
)

df_problematicos.to_csv(
    salida_problematicos,
    index=False,
    encoding="utf-8-sig"
)


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
# FINAL
# ============================================================

print()

print(
    salida_bt
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

print()

print("=" * 78)
print("✅ BACKTEST ADAPTATIVO V2 COMPLETADO")
print("=" * 78)
print()

