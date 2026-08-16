import requests
import json

url = "https://cf.biwenger.com/api/v2/competitions/la-liga/data?lang=es&score=2"

print("Conectando con Biwenger...")

respuesta = requests.get(url, timeout=20)

print("Código HTTP:", respuesta.status_code)

if respuesta.status_code == 200:
    datos = respuesta.json()

    print("¡Conexión correcta!")
    print("Tipo de respuesta:", type(datos))

    print("\nPrimeras claves recibidas:")
    print(list(datos.keys())[:20])

    with open("datos/biwenger_prueba.json", "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)

    print("\nDatos guardados en:")
    print("C:\\FantasyLaLiga\\datos\\biwenger_prueba.json")

else:
    print("Biwenger ha devuelto un error.")
    print(respuesta.text[:500])