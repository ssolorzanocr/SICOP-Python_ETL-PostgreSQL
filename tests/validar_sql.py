"""Valida estaticamente las consultas del prototipo contra el esquema real
definido en 'Paso 1 - script_creacion_tablas_proyecto_sicop_v2.sql'.

No necesita conexion a PostgreSQL: usa sqlglot para parsear cada consulta y
verificar que toda columna referenciada exista en la tabla correspondiente.
"""
import re
import sys

import sqlglot
from sqlglot.optimizer.qualify import qualify

# Esquema del modelo final (tomado del DDL del Paso 1)
SCHEMA = {
    "dim_proveedores": {
        "cedula_proveedor": "VARCHAR", "nombre_proveedor": "VARCHAR",
        "tipo_proveedor": "VARCHAR", "tamano": "VARCHAR",
        "provincia": "VARCHAR", "canton": "VARCHAR", "distrito": "VARCHAR",
    },
    "dim_instituciones": {
        "cedula_institucion": "VARCHAR", "nombre_institucion": "VARCHAR",
        "provincia": "VARCHAR", "canton": "VARCHAR", "distrito": "VARCHAR",
    },
    "dim_catalogo_codigo_identificacion_producto": {
        "cod_producto": "BIGINT", "descripcion_producto": "VARCHAR",
        "segmento": "INT", "nombre_segmento": "VARCHAR", "familia": "INT",
        "clases": "INT", "mercancias": "INT", "nombre_mercancia": "VARCHAR",
    },
    "lineas_carteles": {
        "nro_sicop": "VARCHAR", "nro_procedimiento": "VARCHAR",
        "nro_sicop_nro_linea": "VARCHAR", "nombre_cartel": "VARCHAR",
        "status_cartel": "VARCHAR", "clasificacion_cartel": "VARCHAR",
        "monto_estimado_cartel_crc": "DECIMAL", "nro_linea": "INT",
        "nro_partida": "INT", "cod_producto": "BIGINT", "cantidad": "DECIMAL",
        "precio_unitario_estimado": "DECIMAL",
        "monto_total_linea_estimado": "DECIMAL", "tipo_moneda": "VARCHAR",
        "tipo_cambio_crc": "DECIMAL", "cedula_institucion": "VARCHAR",
        "tipo_procedimiento": "VARCHAR", "modalidad_procedimiento": "VARCHAR",
        "fecha_publicacion": "TIMESTAMP", "fecha_apertura": "TIMESTAMP",
    },
    "lineas_ofertas": {
        "nro_oferta_nro_linea": "VARCHAR", "cedula_proveedor": "VARCHAR",
        "fecha_oferta_presentada": "TIMESTAMP", "tipo_oferta": "VARCHAR",
        "nro_oferta": "VARCHAR", "cod_producto": "BIGINT",
        "nro_sicop": "VARCHAR", "nro_linea": "INT",
        "nro_sicop_nro_linea": "VARCHAR", "cantidad_ofertada": "DECIMAL",
        "precio_unitario_ofertado": "DECIMAL", "tipo_moneda": "VARCHAR",
        "tipo_cambio_crc": "DECIMAL",
    },
    "lineas_adjudicadas": {
        "nro_sicop_nro_linea": "VARCHAR", "nro_sicop": "VARCHAR",
        "nro_oferta": "VARCHAR", "nro_procedimiento": "VARCHAR",
        "nro_linea": "INT", "descr_procedimiento": "VARCHAR",
        "cantidad_adjudicada": "DECIMAL",
        "precio_unitario_adjudicado": "DECIMAL",
        "monto_adjudicado_linea": "DECIMAL", "cedula_institucion": "VARCHAR",
        "fecha_adjud_firme": "DATE", "cedula_proveedor": "VARCHAR",
        "cod_producto": "BIGINT", "moneda_adjudicada": "VARCHAR",
        "tipo_cambio_crc": "DECIMAL",
    },
}


def extraer_consultas(ruta_app: str) -> dict:
    """Saca los bloques text(\"\"\"...\"\"\") de app.py junto al nombre de la
    funcion que los contiene."""
    codigo = open(ruta_app, encoding="utf-8").read()
    consultas = {}
    funcion_actual = "modulo"
    for bloque in re.split(r"\ndef ", codigo):
        m = re.match(r"(\w+)", bloque)
        if m:
            funcion_actual = m.group(1)
        for sql in re.findall(r'text\("""(.*?)"""\)', bloque, re.S):
            consultas.setdefault(funcion_actual, []).append(sql)
        for sql in re.findall(r'text\("(.*?)"\)', bloque):
            consultas.setdefault(funcion_actual, []).append(sql)
    return consultas


def normalizar(sql: str) -> str:
    """Sustituye los parametros bind por literales para poder parsear."""
    sql = sql.replace(":segmento", "'Equipos y suministros medicos'")
    sql = sql.replace(":meses", "12")
    sql = sql.replace(":limite", "30")
    return sql


def main():
    ruta_app = sys.argv[1] if len(sys.argv) > 1 else "app.py"
    consultas = extraer_consultas(ruta_app)

    total, fallos = 0, 0
    for funcion, lista in consultas.items():
        for i, sql in enumerate(lista, 1):
            total += 1
            etiqueta = f"{funcion}[{i}]"
            try:
                arbol = sqlglot.parse_one(normalizar(sql), dialect="postgres")
            except Exception as e:
                fallos += 1
                print(f"FALLA PARSEO  {etiqueta}: {e}")
                continue
            try:
                qualify(arbol, schema=SCHEMA, dialect="postgres")
                print(f"OK            {etiqueta}")
            except Exception as e:
                fallos += 1
                print(f"FALLA COLUMNA {etiqueta}: {e}")

    print(f"\n{total - fallos}/{total} consultas validadas contra el esquema.")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
