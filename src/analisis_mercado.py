import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

HISTORICO_FILE = BASE_DIR / "datos" / "historico_precios.csv"
JUGADORES_FILE = BASE_DIR / "datos" / "jugadores_laliga.csv"


def cargar_datos():

    historico = pd.read_csv(HISTORICO_FILE)
    jugadores = pd.read_csv(JUGADORES_FILE)

    historico["date"] = pd.to_datetime(historico["date"])

    historico["marketValue"] = pd.to_numeric(
        historico["marketValue"],
        errors="coerce"
    )

    # Añadimos la posición
    historico = historico.merge(
        jugadores[["id", "positionId"]],
        left_on="player_id",
        right_on="id",
        how="left"
    )

    # Solo futbolistas: 1 portero, 2 defensa,
    # 3 centrocampista, 4 delantero
    historico = historico[
        historico["positionId"].isin([1, 2, 3, 4])
    ].copy()

    return historico


def precio_mas_cercano(grupo, fecha_objetivo):

    if grupo.empty:
        return None

    diferencias = abs(
        grupo["date"] - fecha_objetivo
    )

    indice = diferencias.idxmin()

    return grupo.loc[indice, "marketValue"]


def calcular_variaciones(df):

    resultados = []

    fecha_maxima = df["date"].max()

    for player_id, grupo in df.groupby("player_id"):

        grupo = grupo.sort_values("date")

        actual = grupo.iloc[-1]

        precio_actual = actual["marketValue"]

        fecha_actual = actual["date"]

        precio_1d = precio_mas_cercano(
            grupo,
            fecha_actual - pd.Timedelta(days=1)
        )

        precio_3d = precio_mas_cercano(
            grupo,
            fecha_actual - pd.Timedelta(days=3)
        )

        precio_7d = precio_mas_cercano(
            grupo,
            fecha_actual - pd.Timedelta(days=7)
        )

        def variacion(precio_anterior):

            if precio_anterior is None:
                return None

            if precio_anterior == 0:
                return None

            return (
                (precio_actual / precio_anterior) - 1
            ) * 100

        resultados.append({

            "player_id": player_id,

            "nickname": actual["nickname"],

            "positionId": actual["positionId"],

            "precio_actual": precio_actual,

            "variacion_1d": variacion(precio_1d),

            "variacion_3d": variacion(precio_3d),

            "variacion_7d": variacion(precio_7d)

        })

    return pd.DataFrame(resultados)


def mostrar_top(df):

    print()
    print("=" * 65)
    print("🔥 TOP 20 SUBIDAS — ÚLTIMOS 7 DÍAS")
    print("=" * 65)

    subidas = (
        df
        .dropna(subset=["variacion_7d"])
        .sort_values("variacion_7d", ascending=False)
        .head(20)
    )

    for _, jugador in subidas.iterrows():

        print(
            f"{jugador['nickname']:<25}"
            f"{jugador['variacion_7d']:>8.2f}%"
            f"   {jugador['precio_actual']:>12,.0f} €"
        )

    print()
    print("=" * 65)
    print("🔻 TOP 20 CAÍDAS — ÚLTIMOS 7 DÍAS")
    print("=" * 65)

    caidas = (
        df
        .dropna(subset=["variacion_7d"])
        .sort_values("variacion_7d")
        .head(20)
    )

    for _, jugador in caidas.iterrows():

        print(
            f"{jugador['nickname']:<25}"
            f"{jugador['variacion_7d']:>8.2f}%"
            f"   {jugador['precio_actual']:>12,.0f} €"
        )


def main():

    print("Cargando datos...")

    df = cargar_datos()

    print(
        f"Registros de futbolistas: {len(df)}"
    )

    print(
        f"Futbolistas con histórico: "
        f"{df['player_id'].nunique()}"
    )

    print(
        f"Fecha más reciente: "
        f"{df['date'].max()}"
    )

    resultados = calcular_variaciones(df)

    mostrar_top(resultados)


if __name__ == "__main__":
    main()