"""Prueba de humo de las 3 páginas, sin navegador (AppTest de Streamlit).

Ejecuta cada página, verifica que no lance excepciones e imprime los KPI. En UC2 y
UC3 además simula una búsqueda de proveedor. Uso, desde la carpeta app:
    python tests/prueba_paginas.py
Requiere sicop.duckdb accesible (ver datos.py).
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

CARPETA_APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CARPETA_APP))

fallos = 0
for pagina in ("uc1_demanda.py", "uc2_proveedores.py", "uc3_prediccion.py"):
    at = AppTest.from_file(str(CARPETA_APP / "paginas" / pagina), default_timeout=180).run()
    errores = [e.value for e in at.exception]
    print(pagina, "EXC:", errores[:2], "ERR:", [e.value for e in at.error][:2])
    fallos += len(errores)
    if pagina.startswith("uc1"):
        print("  ", [(m.label, m.value) for m in at.metric])
    else:
        at.text_input[0].input("3101").run()
        errores = [e.value for e in at.exception]
        fallos += len(errores)
        print("   búsqueda EXC:", errores[:2], "métricas:", [(m.label, m.value) for m in at.metric][:3])

print("OK" if fallos == 0 else f"FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
