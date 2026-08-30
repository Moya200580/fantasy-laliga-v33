"""
Publica en X (Twitter) el contenido de datos/post_diario_v3_3.txt.

Si el fichero contiene varios tweets marcados con
"[[[ TWEET n/N ... ]]]" (generados por generar_post_variado.py cuando
el contenido no cabe en un único tweet), los publica como un hilo:
el primero como tweet normal, y cada uno siguiente como respuesta al
anterior.

Usa las 4 claves de OAuth 1.0a (permiso "Leer y escribir") guardadas
como secrets de GitHub:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
"""

import os
import re
import sys
import time
from pathlib import Path

import tweepy

BASE_DIR = Path(__file__).resolve().parent.parent
POST_FILE = BASE_DIR / "datos" / "post_diario_v3_3.txt"

# Patrón que marca el inicio de cada tweet dentro del fichero, tal
# como los escribe generar_post_variado.py:
# [[[ TWEET 1/2 — 228 caracteres ]]]
PATRON_CABECERA = re.compile(r"\[\[\[\s*TWEET\s+\d+/\d+.*?\]\]\]\s*\n?")


def cargar_tweets():
    texto = POST_FILE.read_text(encoding="utf-8").strip()
    if not texto:
        raise RuntimeError("El fichero post_diario_v3_3.txt está vacío")

    if "[[[ TWEET" not in texto:
        return [texto]

    partes = PATRON_CABECERA.split(texto)
    tweets = [p.strip() for p in partes if p.strip()]
    if not tweets:
        raise RuntimeError("No se pudo extraer ningún tweet del fichero")
    return tweets


def main():
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )

    tweets = cargar_tweets()
    print(f"Se van a publicar {len(tweets)} tweet(s) en hilo.")

    id_anterior = None
    for i, texto in enumerate(tweets, 1):
        try:
            if id_anterior is None:
                resp = client.create_tweet(text=texto)
            else:
                resp = client.create_tweet(text=texto, in_reply_to_tweet_id=id_anterior)
        except tweepy.errors.TweepyException as e:
            print(f"ERROR al publicar el tweet {i}/{len(tweets)}: {e}", file=sys.stderr)
            raise

        id_anterior = resp.data["id"]
        print(f"✓ Tweet {i}/{len(tweets)} publicado. ID: {id_anterior}")

        if i < len(tweets):
            time.sleep(3)  # pequeña pausa entre tweets del mismo hilo

    print("Hilo publicado correctamente.")


if __name__ == "__main__":
    main()