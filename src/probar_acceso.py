import os
from dotenv import load_dotenv
from pybiwenger import authenticate, PlayersAPI

load_dotenv()

usuario = os.getenv("BIWENGER_USERNAME")
password = os.getenv("BIWENGER_PASSWORD")

if not usuario or not password:
    print("ERROR: No se han encontrado las credenciales.")
    raise SystemExit(1)

print("Credenciales encontradas.")
print("Iniciando autenticación...")

authenticate(usuario, password)

print("Autenticación configurada.")

try:
    api = PlayersAPI()

    print("Consultando jugadores...")
    jugadores = list(api.get_all_players())

    print(f"Jugadores encontrados: {len(jugadores)}")

    print("\nPrimeros jugadores:")

    for jugador in jugadores[:10]:
        print(jugador)

except Exception as e:
    print("\nERROR:")
    print(type(e).__name__)
    print(str(e))