"""Prueba de renderizado del prototipo SIN necesidad de PostgreSQL.

Sustituye las consultas a la base de datos por datos ficticios y ejecuta
app.py completo dentro del simulador oficial de Streamlit (AppTest). Sirve
para verificar que toda la capa de presentación funciona: los KPIs, los
gráficos de Altair, el formateo de colones y el renombrado de columnas de
la tabla de detalle.

Uso:
    .venv\\Scripts\\python.exe tests\\test_render_sin_bd.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# En Windows la consola o una redirección a archivo pueden usar cp1252, que
# no sabe imprimir "₡" ni algunos acentos. Forzamos UTF-8 para que la prueba
# no falle por el simple hecho de mostrar un monto en colones.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FECHA_MAX = dt.datetime(2026, 6, 30)


# ------------------------------------------------------------------
# Datos ficticios: una tabla por consulta del prototipo
# ------------------------------------------------------------------

def _df_segmentos() -> pd.DataFrame:
    return pd.DataFrame({
        "nombre_segmento": [
            "Equipos y suministros médicos",
            "Equipos y suministros de oficina",
            "Servicios de construcción y mantenimiento",
        ],
        "lineas_publicadas": [6073, 4492, 3709],
    })


def _df_kpis() -> pd.DataFrame:
    return pd.DataFrame({
        "carteles_publicados": [1284],
        "monto_adjudicado_total": [11609456789.45],
        "proveedores_distintos": [312],
        "promedio_ofertas_por_linea": [3.7],
    })


def _df_instituciones() -> pd.DataFrame:
    return pd.DataFrame({
        "nombre_institucion": [
            "Caja Costarricense de Seguro Social",
            "Instituto Costarricense de Electricidad",
            "Universidad Nacional",
        ],
        "carteles_publicados": [812, 233, 118],
        # la tercera no tiene adjudicaciones -> NULL a propósito
        "dias_mediana_adjudicacion": [98.0, 143.5, None],
    })


def _df_precios() -> pd.DataFrame:
    return pd.DataFrame({
        "razon_adj_est_mediana": [0.876],
        "razon_of_est_mediana": [0.912],
        "lineas_adjudicadas_con_precio": [1044],
        "lineas_ofertadas_con_precio": [3860],
    })


def _df_precios_por_producto() -> pd.DataFrame:
    return pd.DataFrame({
        "cod_producto": [4017150100123456, 4017160200234567, 4017170300345678],
        "producto": ["TUBERÍA PVC 100 mm", "VÁLVULA DE COMPUERTA 2\"", "BOMBA CENTRÍFUGA 5 HP"],
        "carteles": [214, 97, 41],
        "precio_estimado_mediana": [12500.0, 48000.0, 1350000.0],
        "precio_ofertado_mediana": [11800.0, None, 1290000.0],   # NULL a propósito
        "precio_adjudicado_mediana": [11200.0, 45500.0, None],   # NULL a propósito
    })


def _df_tiempos() -> pd.DataFrame:
    return pd.DataFrame({
        "dias_mediana": [121.0],
        "dias_p25": [64.0],
        "dias_p75": [198.0],
        "lineas_adjudicadas": [1044],
    })


def _df_ranking() -> pd.DataFrame:
    return pd.DataFrame({
        "nombre_proveedor": ["Proveedor Alfa S.A.", "Proveedor Beta Ltda."],
        "carteles_ganados": [47, 31],
        "monto_total_adjudicado": [2450000000.0, 1180000000.0],
    })


def _df_evolucion() -> pd.DataFrame:
    meses = pd.to_datetime(["2026-04-01", "2026-05-01", "2026-06-01"])
    return pd.DataFrame({
        "mes": list(meses) * 2,
        "cantidad": [120, 143, 98, 87, 101, 64],
        "tipo": ["Publicados"] * 3 + ["Adjudicados"] * 3,
    })


def _df_detalle() -> pd.DataFrame:
    return pd.DataFrame({
        "nro_sicop": ["20260601000100001", "20260528000100002"],
        "nombre_cartel": ["Compra de insumos médicos", "Mantenimiento de equipo"],
        "nombre_institucion": ["Caja Costarricense de Seguro Social", "Universidad Nacional"],
        "fecha_publicacion": pd.to_datetime(["2026-06-01", "2026-05-28"]),
        "fecha_apertura": pd.to_datetime(["2026-06-15", "2026-06-10"]),
        "monto_estimado_cartel_crc": [45000000.0, None],  # incluye NULL a propósito
        "status_cartel": ["En recepción de ofertas", "Adjudicado"],
    })


def _fake_read_sql_query(sql, con, params=None, **kwargs) -> pd.DataFrame:
    """Devuelve la tabla ficticia que corresponde según el texto del SQL."""
    texto = str(sql)
    # Las consultas más específicas van primero para que una palabra común
    # (p. ej. "nombre_institucion") no capture la consulta equivocada.
    if "razon_adj_est_mediana" in texto:
        return _df_precios()
    if "precio_estimado_mediana" in texto:
        return _df_precios_por_producto()
    if "dias_p25" in texto:
        return _df_tiempos()
    if "lineas_publicadas" in texto:
        return _df_segmentos()
    if "promedio_ofertas_por_linea" in texto:
        return _df_kpis()
    if "monto_total_adjudicado" in texto:
        return _df_ranking()
    if "'Publicados'" in texto or "UNION ALL" in texto:
        return _df_evolucion()
    if "DISTINCT ON" in texto:
        return _df_detalle()
    if "nombre_institucion" in texto:
        return _df_instituciones()
    raise AssertionError(f"Consulta no reconocida por la prueba:\n{texto[:300]}")


def _fake_engine() -> MagicMock:
    """Engine simulado: solo necesita responder a .connect() y, dentro del
    contexto, a .execute(...).scalar() para la fecha de referencia."""
    conn = MagicMock()
    conn.execute.return_value.scalar.return_value = FECHA_MAX

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    return engine


# ------------------------------------------------------------------
# Prueba
# ------------------------------------------------------------------

def ejecutar_app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
    at.secrets["postgres"] = {
        "host": "localhost", "port": "5432", "database": "proyecto_sicop_v1",
        "user": "postgres", "password": "ficticia",
    }

    with patch("sqlalchemy.create_engine", return_value=_fake_engine()), \
         patch("pandas.read_sql_query", side_effect=_fake_read_sql_query):
        at.run()
    return at


def main() -> int:
    at = ejecutar_app()

    problemas = []

    if at.exception:
        for exc in at.exception:
            problemas.append(f"EXCEPCIÓN: {exc.value}")

    if at.error:
        for err in at.error:
            problemas.append(f"st.error mostrado: {err.value}")

    # La pantalla debe contener 6 KPIs, 3 gráficos y 2 tablas (precios y detalle).
    if len(at.metric) != 6:
        problemas.append(f"Se esperaban 6 KPIs (st.metric), hay {len(at.metric)}")
    if len(at.selectbox) != 1:
        problemas.append(f"Se esperaba 1 selectbox de segmento, hay {len(at.selectbox)}")
    if len(at.slider) != 1:
        problemas.append(f"Se esperaba 1 slider de meses, hay {len(at.slider)}")
    if len(at.dataframe) != 2:
        problemas.append(f"Se esperaban 2 tablas (precios y detalle), hay {len(at.dataframe)}")

    # Los KPIs nuevos deben mostrar el formato esperado con los datos ficticios
    valores = {m.label: str(m.value) for m in at.metric}
    if valores.get("Precio adjudicado vs. estimado") != "-12,4 %":
        problemas.append(
            "El KPI de precio no formateó la razón 0,876 como '-12,4 %': "
            f"mostró {valores.get('Precio adjudicado vs. estimado')!r}")
    if valores.get("Días hasta adjudicación") != "121 días":
        problemas.append(
            "El KPI de tiempos no formateó la mediana 121.0 como '121 días': "
            f"mostró {valores.get('Días hasta adjudicación')!r}")

    print("=" * 62)
    print("PRUEBA DE RENDERIZADO (sin base de datos)")
    print("=" * 62)
    if at.metric:
        for m in at.metric:
            print(f"  KPI  {m.label}: {m.value}")
    print(f"  Selectbox: {len(at.selectbox)} | Slider: {len(at.slider)} | "
          f"Tablas: {len(at.dataframe)}")

    # Comprobar que la interacción con el filtro no rompe nada
    if at.selectbox:
        with patch("sqlalchemy.create_engine", return_value=_fake_engine()), \
             patch("pandas.read_sql_query", side_effect=_fake_read_sql_query):
            at.selectbox[0].select("Equipos y suministros de oficina").run()
        if at.exception:
            problemas.append(
                f"EXCEPCIÓN al cambiar de segmento: {at.exception[0].value}")
        else:
            print("  Cambio de segmento: OK")

    print("-" * 62)
    if problemas:
        for p in problemas:
            print(f"  FALLA: {p}")
        print(f"\n{len(problemas)} problema(s) encontrado(s).")
        return 1

    print("  Todo correcto: la capa de presentación funciona con datos simulados.")
    print("  NOTA: esto NO valida los datos reales; para eso hay que ejecutar")
    print("        tests/test_consultas_con_bd.py contra proyecto_sicop_v1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
