import pandas as pd
import numpy as np

MIN_APARICIONES_PENALIZACION = 3
VENTANA_MEMORIA = 8
PENALIZACION_MAXIMA = 25.0
UMBRAL_ACIERTO_BUENO = 60.0
PESO_RENTABILIDAD_V3 = 1.10
PESO_FALLOS_V3 = 0.18
PESO_RACHA_FALLOS_V3 = 1.75
PESO_DETERIORO_V3 = 0.45
MAX_RENTABILIDAD_V3 = 10.0
MAX_FALLOS_V3 = 8.0
MAX_RACHA_V3 = 8.0
MAX_DETERIORO_V3 = 7.0


def calcular_score_base(precio, var_7d, var_3d, var_1d, last_season_points):
    if pd.isna(last_season_points):
        last_season_points = 0
    precio_millones = max(precio / 1_000_000, 0.000001)
    rendimiento_ratio = last_season_points / precio_millones
    score_rendimiento = np.clip(rendimiento_ratio * 0.25, 0, 40)
    score_tendencia = var_7d * 0.50 + var_3d * 0.30 + var_1d * 0.20
    score_tendencia = np.clip(score_tendencia * 1.5, 0, 40)
    aceleracion = var_1d - (var_3d / 3)
    score_aceleracion = 0
    if var_7d > 5 and var_3d > 2 and var_1d > 0:
        score_aceleracion += 5
    if var_7d > 10 and var_3d > 4 and var_1d > 1:
        score_aceleracion += 5
    valor_historico = last_season_points / precio_millones
    score_historico = np.clip(valor_historico / 100 * 15, 0, 15)
    score_precio = np.clip(15 - precio_millones, 0, 15)
    score_precio_final = score_precio / 15 * 10
    score_fichaje = score_tendencia + score_aceleracion + score_historico + score_precio_final
    penalizacion_deterioro = 0
    if var_7d < -5:
        penalizacion_deterioro += 5
    if var_7d < -10:
        penalizacion_deterioro += 8
    if var_7d < -15:
        penalizacion_deterioro += 12
    if var_7d < 0 and var_1d < 0:
        penalizacion_deterioro += 5
    score_fichaje -= penalizacion_deterioro
    score_fichaje = np.clip(score_fichaje, 0, 100)
    score_especulacion = var_7d * 0.50 + var_3d * 0.30 + var_1d * 0.20
    if aceleracion > 1:
        score_especulacion += 5
    if aceleracion > 2:
        score_especulacion += 5
    if precio < 5_000_000 and var_7d > 10:
        score_especulacion += 8
    if precio < 10_000_000 and var_7d > 15:
        score_especulacion += 5
    if var_7d < 0:
        score_especulacion -= 10
    if var_7d < 0 and var_1d < 0:
        score_especulacion -= 10
    score_especulacion = np.clip(score_especulacion, 0, 100)
    precio_teorico = last_season_points * 50_000
    potencial_bruto = ((precio_teorico - precio) / max(precio, 1)) * 100
    potencial_bruto = np.clip(potencial_bruto, -100, 200)
    potencial_subida = (potencial_bruto + 100) / 300 * 100
    if var_7d > 10 and var_3d > 3 and var_1d > 0:
        potencial_subida += 10
    if var_7d > 20 and var_3d > 7 and var_1d > 2:
        potencial_subida += 10
    potencial_subida = np.clip(potencial_subida, 0, 100)
    score = score_fichaje * 0.60 + score_especulacion * 0.20 + potencial_subida * 0.20
    return float(np.clip(score, 0, 100))


def resultado_memoria_vacio():
    return {"penalizacion": 0.0, "apariciones": 0, "rentabilidad_media_7d": 0.0, "acierto_7d": 100.0, "fallos_consecutivos": 0, "deterioro_reciente": 0.0}


def calcular_penalizacion_v3(player_id, fecha, historial):
    if historial.empty:
        return resultado_memoria_vacio()
    jugador = historial[historial["player_id"] == player_id].copy()
    jugador = jugador[jugador["fecha"] < fecha].copy()
    if jugador.empty:
        return resultado_memoria_vacio()
    jugador = jugador.sort_values("fecha")
    if len(jugador) > VENTANA_MEMORIA:
        jugador = jugador.tail(VENTANA_MEMORIA)
    apariciones = len(jugador)
    rentabilidades = pd.to_numeric(jugador["rentabilidad_7d"], errors="coerce").dropna()
    if rentabilidades.empty:
        return {"penalizacion": 0.0, "apariciones": apariciones, "rentabilidad_media_7d": 0.0, "acierto_7d": 0.0, "fallos_consecutivos": 0, "deterioro_reciente": 0.0}
    rentabilidad_media = rentabilidades.mean()
    acierto = (rentabilidades > 0).mean() * 100
    if apariciones < MIN_APARICIONES_PENALIZACION:
        return {"penalizacion": 0.0, "apariciones": apariciones, "rentabilidad_media_7d": float(rentabilidad_media), "acierto_7d": float(acierto), "fallos_consecutivos": 0, "deterioro_reciente": 0.0}
    fallos = int((rentabilidades <= 0).sum())
    porcentaje_fallos = (fallos / len(rentabilidades)) * 100
    fallos_consecutivos = 0
    for resultado in reversed(rentabilidades.tolist()):
        if resultado <= 0:
            fallos_consecutivos += 1
        else:
            break
    if len(rentabilidades) >= 6:
        mitad = len(rentabilidades) // 2
        antigua = rentabilidades.iloc[:mitad].mean()
        reciente = rentabilidades.iloc[mitad:].mean()
        deterioro_reciente = antigua - reciente
    else:
        deterioro_reciente = 0.0
    componente_rentabilidad = 0.0
    if rentabilidad_media < 0:
        componente_rentabilidad = min(abs(rentabilidad_media) * PESO_RENTABILIDAD_V3, MAX_RENTABILIDAD_V3)
    componente_fallos = min((porcentaje_fallos / 100) * MAX_FALLOS_V3, MAX_FALLOS_V3)
    componente_racha = min(fallos_consecutivos * PESO_RACHA_FALLOS_V3, MAX_RACHA_V3)
    componente_deterioro = 0.0
    if deterioro_reciente > 2:
        componente_deterioro = min(deterioro_reciente * PESO_DETERIORO_V3, MAX_DETERIORO_V3)
    if rentabilidad_media > 0 and acierto >= UMBRAL_ACIERTO_BUENO and fallos_consecutivos == 0:
        componente_rentabilidad = 0.0
        componente_deterioro = 0.0
        componente_fallos = min(componente_fallos, 1.5)
    penalizacion = np.clip(componente_rentabilidad + componente_fallos + componente_racha + componente_deterioro, 0, PENALIZACION_MAXIMA)
    return {"penalizacion": float(penalizacion), "apariciones": int(apariciones), "rentabilidad_media_7d": float(rentabilidad_media), "acierto_7d": float(acierto), "fallos_consecutivos": int(fallos_consecutivos), "deterioro_reciente": float(deterioro_reciente)}
