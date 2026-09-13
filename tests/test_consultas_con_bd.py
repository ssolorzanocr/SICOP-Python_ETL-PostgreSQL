"""Prueba de humo CONTRA la base de datos real (proyecto_sicop_v1).

Extrae las consultas directamente de app.py (sin duplicarlas) y las ejecuta
sobre la base real, reportando cuántas filas devuelve cada una. Sirve para
confirmar que el modelo está cargado y que el prototipo va a mostrar datos.

Requisitos:
  - PostgreSQL iniciado y proyecto_sicop_v1 cargada (Pasos 1 a 4).
  - .streamlit/secrets.toml creado (ver .streamlit/secrets.toml.example).

Uso:
    .venv\\Scripts\\python.exe tests\\test_consultas_con_bd.py
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parent.parent
SECRETS = RAIZ / ".streamlit" / "secrets.toml"
APP = RAIZ / "app.py"

TABLAS_ESPERADAS = [
    "dim_proveedores",
    "dim_instituciones",
    "dim_catalogo_codigo_identificacion_producto",
    "lineas_carteles",
    "lineas_ofertas",
    "lineas_adjudicadas",
]


def cargar_engine():
    if not SECRETS.exists():
        print(f"FALTA el archivo {SECRETS}")
        print("Copia .streamlit/secrets.toml.example a .streamlit/secrets.toml")
        print("y coloca ahí tu contraseña de PostgreSQL.")
        sys.exit(2)

    with open(SECRETS, "rb") as f:
        db = tomllib.load(f)["postgres"]

    url = (
        f"postgresql+psycopg2://{db['user']}:{db['password']}"
        f"@{db['host']}:{db['port']}/{db['database']}"
    )
    return create_engine(url, pool_pre_ping=True)


def extraer_consultas() -> dict[str, str]:
    """Devuelve {nombre_funcion: sql} leyendo los bloques text(...) de app.py."""
    codigo = APP.read_text(encoding="utf-8")
    consultas: dict[str, str] = {}
    for bloque in re.split(r"\ndef ", codigo):
        m = re.match(r"(\w+)", bloque)
        if not m:
            continue
        nombre = m.group(1)
        encontradas = re.findall(r'text\("""(.*?)"""\)', bloque, re.S)
        encontradas += re.findall(r'text\("(.*?)"\)', bloque)
        for sql in encontradas:
            consultas[nombre] = sql
    return consultas


def main() -> int:
    engine = cargar_engine()
    problemas: list[str] = []

    print("=" * 66)
    print("PRUEBA CONTRA LA BASE DE DATOS REAL (proyecto_sicop_v1)")
    print("=" * 66)

    # 1. Conexión
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version();")).scalar()
        print(f"  Conexión OK: {version.split(',')[0]}")
    except Exception as e:
        print(f"  FALLA de conexión: {e}")
        return 1

    # 2. Conteo de filas por tabla
    print("\n  Filas por tabla:")
    with engine.connect() as conn:
        for tabla in TABLAS_ESPERADAS:
            try:
                n = conn.execute(text(f"SELECT COUNT(*) FROM {tabla};")).scalar()
                marca = "" if n else "   <-- VACÍA"
                print(f"    {tabla:<46} {n:>10,}{marca}")
                if not n:
                    problemas.append(f"La tabla {tabla} está vacía")
            except Exception as e:
                print(f"    {tabla:<46} ERROR: {e}")
                problemas.append(f"No se pudo consultar {tabla}: {e}")

    # 3. Segmento con más actividad (se usa como parámetro de las demás)
    consultas = extraer_consultas()
    sql_segmentos = consultas.get("get_segmentos")
    if not sql_segmentos:
        problemas.append("No se pudo extraer get_segmentos de app.py")
        return _resumen(problemas)

    with engine.connect() as conn:
        df_seg = pd.read_sql_query(text(sql_segmentos), conn)

    if df_seg.empty:
        problemas.append(
            "get_segmentos no devolvió filas: falta ejecutar el Paso 4 "
            "(carga del catálogo de productos)"
        )
        return _resumen(problemas)

    segmento = df_seg.iloc[0]["nombre_segmento"]
    print(f"\n  Segmentos disponibles: {len(df_seg)}")
    print(f"  Segmento de prueba: «{segmento}» "
          f"({df_seg.iloc[0]['lineas_publicadas']:,} líneas)")

    # 4. Ejecutar el resto de consultas con ese segmento
    parametros = {"segmento": segmento, "meses": 12, "limite": 30}
    print("\n  Consultas del prototipo:")
    for nombre, sql in consultas.items():
        if nombre in ("get_segmentos", "get_periodo_referencia"):
            continue
        usados = {k: v for k, v in parametros.items() if f":{k}" in sql}
        try:
            with engine.connect() as conn:
                df = pd.read_sql_query(text(sql), conn, params=usados)
            estado = "" if not df.empty else "   <-- SIN FILAS"
            print(f"    {nombre:<28} {len(df):>6} filas{estado}")
            if df.empty:
                problemas.append(f"{nombre} no devolvió filas para «{segmento}»")
        except Exception as e:
            print(f"    {nombre:<28} ERROR: {e}")
            problemas.append(f"{nombre} falló: {e}")

    return _resumen(problemas)


def _resumen(problemas: list) -> int:
    print("-" * 66)
    if problemas:
        for p in problemas:
            print(f"  FALLA: {p}")
        print(f"\n{len(problemas)} problema(s). Revisa los Pasos 1 a 4 del ETL.")
        return 1
    print("  Todo correcto: la base está cargada y el prototipo tendrá datos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
