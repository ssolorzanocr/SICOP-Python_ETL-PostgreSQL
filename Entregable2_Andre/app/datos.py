"""
Capa de datos de la aplicación: conexión a DuckDB y reglas comunes.

La aplicación lee el archivo `sicop.duckdb` que publica el pipeline automatizado
del grupo (repositorio Modelo_predictivo_SICOP, release `datos_actuales_sicop`).
Todo el acceso a datos pasa por este módulo: si mañana la base vuelve a estar en
un servidor (PostgreSQL/Supabase), solo cambia este archivo.

Ruta del archivo, en orden de prioridad:
    1. st.secrets["duckdb"]["ruta"]   (.streamlit/secrets.toml)
    2. variable de entorno SICOP_DUCKDB
    3. Modelo_predictivo_SICOP/data/sicop.duckdb en alguna carpeta superior (D:\\mba)
"""

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

CARPETA_APP = Path(__file__).parent
# La app puede vivir en D:\mba\Andre_Entregable2\app o dentro del repo
# (D:\mba\SICOP-Python_ETL-PostgreSQL\Entregable2_Andre\app): se busca el clon de
# Modelo_predictivo_SICOP subiendo de carpeta en carpeta.
RUTAS_CANDIDATAS = [padre / "Modelo_predictivo_SICOP" / "data" / "sicop.duckdb"
                    for padre in CARPETA_APP.parents]
RUTA_POR_DEFECTO = next((r for r in RUTAS_CANDIDATAS if r.exists()), RUTAS_CANDIDATAS[1])
CARPETA_DATOS_APP = CARPETA_APP / "datos"

# Sistema visual común del grupo (skill dataviz). Slots categóricos en orden fijo.
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
GRIS = "#c3c2b7"


def ruta_duckdb() -> Path:
    try:
        return Path(st.secrets["duckdb"]["ruta"])
    except (KeyError, FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        pass
    if os.environ.get("SICOP_DUCKDB"):
        return Path(os.environ["SICOP_DUCKDB"])
    return RUTA_POR_DEFECTO


@st.cache_resource
def conexion() -> duckdb.DuckDBPyConnection:
    """Una conexión de solo lectura para toda la aplicación. Cada consulta usa
    su propio cursor (DuckDB no comparte un cursor entre hilos de Streamlit)."""
    ruta = ruta_duckdb()
    if not ruta.exists():
        raise FileNotFoundError(ruta)
    return duckdb.connect(str(ruta), read_only=True)


def consultar(sql: str, params: list | None = None) -> pd.DataFrame:
    return conexion().cursor().execute(sql, params or []).df()


def a_crc(valor: str, moneda: str, tipo_cambio: str) -> str:
    """Expresión SQL que lleva un precio o monto a colones.

    Regla verificada contra los datos (30/09/2026): `tipo_cambio_crc` contiene el
    tipo de cambio del DÓLAR (~500) en todas las filas, incluso en CRC y EUR.
    Por eso solo se convierte USD; otras monedas (≈0,7 % de las líneas) quedan
    NULL: mejor sin dato que un dato mal convertido."""
    return (f"CASE WHEN {moneda} = 'CRC' THEN {valor} "
            f"WHEN {moneda} = 'USD' AND {tipo_cambio} > 0 THEN {valor} * {tipo_cambio} END")


# ------------------------------------------------------------------
# Formatos (convención costarricense: punto de miles, coma decimal)
# ------------------------------------------------------------------

def colones(valor) -> str:
    if valor is None or pd.isna(valor):
        return "s/d"
    return "₡ {:,.0f}".format(valor).replace(",", ".")


def colones_compacto(valor) -> str:
    """Para tarjetas de KPI, donde el monto completo no cabe: '₡ 2.203,5 M'."""
    if valor is None or pd.isna(valor):
        return "s/d"
    if abs(valor) >= 1e9:
        return f"₡ {valor / 1e9:,.1f} mil M".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"₡ {valor / 1e6:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")


def entero(valor) -> str:
    if valor is None or pd.isna(valor):
        return "s/d"
    return "{:,.0f}".format(valor).replace(",", ".")


def porcentaje(valor, decimales: int = 0) -> str:
    if valor is None or pd.isna(valor):
        return "s/d"
    return f"{valor * 100:.{decimales}f} %".replace(".", ",")


def variacion(razon) -> str:
    """0,88 -> '-12,0 %'; 1,05 -> '+5,0 %'."""
    if razon is None or pd.isna(razon):
        return "s/d"
    return f"{(float(razon) - 1) * 100:+.1f} %".replace(".", ",")


def dias(valor) -> str:
    if valor is None or pd.isna(valor):
        return "s/d"
    return f"{float(valor):.0f} días"


# ------------------------------------------------------------------
# Consultas compartidas
# ------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fecha_maxima():
    return consultar("SELECT MAX(fecha_publicacion) FROM final.fact_lineas_carteles").iat[0, 0]


@st.cache_data(ttl=3600)
def segmentos() -> pd.DataFrame:
    """Segmentos UNSPSC ordenados por volumen de líneas publicadas."""
    return consultar("""
        SELECT p.nombre_segmento, COUNT(*) AS lineas
        FROM final.fact_lineas_carteles c
        JOIN final.dim_productos p ON p.cod_producto = TRY_CAST(c.cod_producto AS BIGINT)
        WHERE p.nombre_segmento IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
    """)


def leer_parquet(nombre: str) -> pd.DataFrame | None:
    ruta = CARPETA_DATOS_APP / nombre
    return pd.read_parquet(ruta) if ruta.exists() else None


def verificar_conexion() -> None:
    """Detiene la página con un mensaje claro si no se encuentra la base."""
    try:
        conexion()
    except FileNotFoundError as error:
        st.error(
            f"No se encontró la base `sicop.duckdb` en `{error}`.\n\n"
            "Descárgala del release `datos_actuales_sicop` del repositorio "
            "Modelo_predictivo_SICOP y colócala en esa ruta, o indica otra ruta en "
            "`.streamlit/secrets.toml` (sección `[duckdb]`, clave `ruta`)."
        )
        st.stop()
