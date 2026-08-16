import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

JUGADORES_FILE = BASE_DIR / "datos" / "jugadores_laliga.csv"
HISTORICO_FILE = BASE_DIR / "datos" / "historico_precios.csv"


def cargar_datos():

    jugadores = pd.read_csv(JUGADORES_FILE)
    historico = pd.read_csv(HISTORICO_FILE)

    # Solo futbolistas
    jugadores = jugadores[
        jugadores["positionId"].isin([1, 2, 3, 4])
    ].copy()

    jugadores["points"] = pd.to_numeric(
        jugadores["points"],
        errors="coerce"
    ).fillna(0)

    jugadores["lastSeasonPoints"] = pd.to_numeric(
        jugadores["lastSeasonPoints"],
        errors="coerce"
    ).fillna(0)

    jugadores["marketValue"] = pd.to_numeric(
        jugadores["marketValue"],
        errors="coerce"
    ).fillna(0)

    # Puntos por millón de euros
    jugadores["puntos_por_millon"] = (
        jugadores["points"] /
        (jugadores["marketValue"] / 1_000_000)
    )

    # Puntos históricos por millón
    jugadores["historico_por_millon"] = (
        jugadores["lastSeasonPoints"] /
        (jugadores["marketValue"] / 1_000_000)
    )

    return jugadores


def mostrar_ranking(df):

    print()
    print("=" * 75)
    print("🏆 RANKING PUNTOS / PRECIO")
    print("=" * 75)

    ranking = (
        df
        .replace([float("inf"), -float("inf")], 0)
        .sort_values(
            "puntos_por_millon",
            ascending=False
        )
        .head(30)
    )

    for _, jugador in ranking.iterrows():

        print(
            f"{jugador['nickname']:<25}"
            f"{jugador['points']:>6.0f} pts"
            f"   {jugador['marketValue']:>12,.0f} €"
            f"   {jugador['puntos_por_millon']:>7.2f}"
        )


def mostrar_historico(df):

    print()
    print("=" * 75)
    print("📊 RENDIMIENTO HISTÓRICO / PRECIO")
    print("=" * 75)

    ranking = (
        df
        .replace([float("inf"), -float("inf")], 0)
        .sort_values(
            "historico_por_millon",
            ascending=False
        )
        .head(30)
    )

    for _, jugador in ranking.iterrows():

        print(
            f"{jugador['nickname']:<25}"
            f"{jugador['lastSeasonPoints']:>6.0f} pts"
            f"   {jugador['marketValue']:>12,.0f} €"
            f"   {jugador['historico_por_millon']:>7.2f}"
        )


def main():

    print("Cargando jugadores...")

    df = cargar_datos()

    print(
        f"Futbolistas analizados: "
        f"{len(df)}"
    )

    mostrar_ranking(df)

    mostrar_historico(df)


if __name__ == "__main__":
    main()