import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
LOG_DIR = BASE_DIR / "resultados"
LOG_DIR.mkdir(exist_ok=True)

PASOS = [
    ("1/3", "Actualizar jugadores", SRC_DIR / "laliga_fantasy.py"),
    ("2/3", "Actualizar histórico de precios", SRC_DIR / "historico_precios.py"),
    ("3/3", "Ejecutar motor V3.3", SRC_DIR / "motor_diario_v3_3.py"),
]


def ejecutar(nombre, script):
    print("=" * 70)
    print(nombre)
    print("=" * 70)
    print(f"Ejecutando: {script.name}")
    print()
    resultado = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BASE_DIR),
        text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            f"El proceso {script.name} terminó con código {resultado.returncode}."
        )


def main():
    inicio = datetime.now()
    print("=" * 70)
    print("ACTUALIZACIÓN DIARIA FANTASY LALIGA — V3.3")
    print("=" * 70)
    print(f"Inicio: {inicio:%Y-%m-%d %H:%M:%S}")
    print()

    try:
        for etiqueta, nombre, script in PASOS:
            if not script.exists():
                raise FileNotFoundError(f"No existe: {script}")
            ejecutar(f"{etiqueta} {nombre}", script)

        fin = datetime.now()
        print()
        print("=" * 70)
        print("✅ ACTUALIZACIÓN COMPLETADA CORRECTAMENTE")
        print("=" * 70)
        print(f"Fin: {fin:%Y-%m-%d %H:%M:%S}")
        print(f"Duración: {fin - inicio}")
        print()
        print("El post diario se encuentra en:")
        print(BASE_DIR / "datos" / "post_diario_v3_3.txt")

    except Exception as exc:
        print()
        print("=" * 70)
        print("❌ ACTUALIZACIÓN NO COMPLETADA")
        print("=" * 70)
        print(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
