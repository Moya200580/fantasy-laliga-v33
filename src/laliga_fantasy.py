import requests
import csv
from pathlib import Path
from datetime import datetime

API_URL = "https://fantasy-api.llt-services.com/api/v1/competition/1/players"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "datos"
DATA_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = DATA_DIR / "jugadores_laliga.csv"


def obtener_jugadores():
    print("Conectando con LALIGA Fantasy...")

    response = requests.get(
        API_URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30
    )

    response.raise_for_status()

    jugadores = response.json()

    print(f"Jugadores recibidos: {len(jugadores)}")

    return jugadores


def guardar_jugadores(jugadores):

    columnas = [
        "id",
        "positionId",
        "nickname",
        "lastSeasonPoints",
        "playerStatus",
        "marketValue",
        "points",
        "averagePoints",
        "teamId",
        "fecha_actualizacion"
    ]

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as archivo:

        writer = csv.DictWriter(
            archivo,
            fieldnames=columnas,
            extrasaction="ignore"
        )

        writer.writeheader()

        fecha = datetime.now().isoformat(timespec="seconds")

        for jugador in jugadores:

            jugador["fecha_actualizacion"] = fecha

            writer.writerow(jugador)

    print(f"Datos guardados en:")
    print(OUTPUT_FILE)


def main():

    jugadores = obtener_jugadores()

    guardar_jugadores(jugadores)

    print()
    print("Proceso terminado correctamente.")


if __name__ == "__main__":
    main()