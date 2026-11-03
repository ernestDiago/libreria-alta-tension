"""
Genera las tablas de referencia de los tests de regresión (tests/referencias/).

Ejecútalo SOLO cuando un cambio en los resultados sea intencionado y lo hayas comprobado:
    python tests/generar_referencias.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from conftest import CARPETA_REFERENCIAS, CASOS_MECANICOS, crear_calculo  # noqa: E402

CARPETA_REFERENCIAS.mkdir(exist_ok=True)

for caso in CASOS_MECANICOS:
    calc = crear_calculo(caso)
    calc.resolver().to_csv(CARPETA_REFERENCIAS / f"{caso}_hipotesis.csv")
    calc.tabla_tendido().to_csv(CARPETA_REFERENCIAS / f"{caso}_tendido.csv")
    print(f"Guardado: {caso}")
