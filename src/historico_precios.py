import requests
import csv
import time
from pathlib import Path

BASE_URL = "https://fantasy-api.llt-services.com/api/v1/competition/1"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "datos"

JUGADORES_FILE = DATA_DIR / "jugadores_laliga.csv"
HISTORICO_FILE = DATA_DIR / "historico_precios.csv"


def obtener_historico(player_id):
    url = f"{BASE_URL}/player/{player_id}/market-value"

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def cargar_jugadores():
    with open(JUGADORES_FILE, encoding="utf-8-sig") as archivo:
        return list(csv.DictReader(archivo))


def main():

    jugadores = cargar_jugadores()

    print(f"Jugadores encontrados: {len(jugadores)}")
    print("Comenzando descarga del histórico...")
    print()

    campos = [
        "player_id",
        "nickname",
        "date",
        "marketValue",
        "bids"
    ]

    # Empezamos un archivo nuevo
    with open(
        HISTORICO_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as archivo:

        writer = csv.DictWriter(
            archivo,
            fieldnames=campos
        )

        writer.writeheader()

        total_registros = 0

        for numero, jugador in enumerate(jugadores, 1):

            player_id = jugador["id"]
            nombre = jugador["nickname"]

            print(
                f"[{numero}/{len(jugadores)}] {nombre}",
                end="",
                flush=True
            )

            try:

                historico = obtener_historico(player_id)

                registros_jugador = 0

                for dato in historico:

                    writer.writerow({
                        "player_id": player_id,
                        "nickname": nombre,
                        "date": dato.get("date"),
                        "marketValue": dato.get("marketValue"),
                        "bids": dato.get("bids", 0)
                    })

                    registros_jugador += 1
                    total_registros += 1

                # Guardar físicamente en disco
                archivo.flush()

                print(
                    f" -> {registros_jugador} registros"
                )

            except Exception as error:

                print(
                    f" -> ERROR: {error}"
                )

            time.sleep(0.15)

    print()
    print("======================================")
    print("HISTÓRICO COMPLETADO")
    print("======================================")
    print(f"Jugadores procesados: {len(jugadores)}")
    print(f"Registros históricos: {total_registros}")
    print(f"Archivo: {HISTORICO_FILE}")


if __name__ == "__main__":
    main()