"""
SICOP - Prototipo de inteligencia de negocio para proveedores MIPYME.

Caso de uso 1 (comportamiento de la demanda institucional):
    "Un proveedor MIPYME quiere descubrir y evaluar los carteles de su
    segmento de producto": elige un segmento de la clasificación UNSPSC
    de SICOP y una ventana de meses, y la aplicación responde en una sola
    pantalla quién compra, cuánto suele costar, cuánta competencia existe
    y quién gana.

Fuente de datos: PostgreSQL (proyecto_sicop_v1), poblado por el pipeline
ETL de 4 pasos del grupo (Observatorio de Compra Pública -> staging ->
modelo dimensional -> catálogo de productos UNSPSC).

Nota de terminología: los códigos de producto de SICOP siguen el estándar
UNSPSC (Naciones Unidas). No confundir con CABYS, el catálogo de bienes y
servicios del Ministerio de Hacienda para facturación electrónica, que es
otro sistema.
"""

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ------------------------------------------------------------------
# Configuración de página
# ------------------------------------------------------------------

st.set_page_config(
    page_title="SICOP - Carteles por segmento",
    layout="wide",
)


# ------------------------------------------------------------------
# Conexión a la base de datos
# ------------------------------------------------------------------

@st.cache_resource
def get_engine() -> Engine:
    """Crea (una sola vez) el engine de SQLAlchemy hacia PostgreSQL.

    Se usa SQLAlchemy en vez de una conexión psycopg2 cruda para que
    pandas no emita el warning de "DBAPI connection not supported",
    sin cambiar el motor de base de datos ni el driver del grupo
    (sigue siendo PostgreSQL vía psycopg2 por debajo).
    """
    db = st.secrets["postgres"]
    url = (
        f"postgresql+psycopg2://{db['user']}:{db['password']}"
        f"@{db['host']}:{db['port']}/{db['database']}"
    )
    return create_engine(url, pool_pre_ping=True)


def formatear_colones(valor) -> str:
    """Formatea un monto como colones costarricenses: '₡ 12.345.678'."""
    if valor is None or pd.isna(valor):
        return "₡ 0"
    return "₡ {:,.0f}".format(valor).replace(",", ".")


# ------------------------------------------------------------------
# Consultas (cacheadas). El parámetro del engine lleva "_" al inicio
# para que Streamlit no intente hashearlo.
# ------------------------------------------------------------------

@st.cache_data(ttl=600)
def get_periodo_referencia(_engine: Engine):
    """Fecha de publicación más reciente disponible en lineas_carteles."""
    query = text("SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles;")
    with _engine.connect() as conn:
        return conn.execute(query).scalar()


@st.cache_data(ttl=600)
def get_segmentos(_engine: Engine) -> pd.DataFrame:
    """Segmentos UNSPSC ordenados por volumen de líneas de cartel
    (no alfabéticamente), para que el selectbox muestre primero los
    segmentos más relevantes para el usuario."""
    query = text("""
        SELECT c.nombre_segmento,
               COUNT(*) AS lineas_publicadas
        FROM lineas_carteles lc
        JOIN dim_catalogo_codigo_identificacion_producto c
            ON lc.cod_producto = c.cod_producto
        WHERE c.nombre_segmento IS NOT NULL
        GROUP BY c.nombre_segmento
        ORDER BY lineas_publicadas DESC;
    """)
    with _engine.connect() as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(ttl=600)
def get_kpis(_engine: Engine, segmento: str, meses: int) -> pd.Series:
    """KPIs del segmento: carteles publicados, monto adjudicado,
    proveedores distintos que ofertaron y promedio de ofertas por línea
    (indicador de competencia)."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        ),
        carteles_seg AS (
            SELECT lc.nro_sicop, lc.nro_linea, lc.nro_sicop_nro_linea
            FROM lineas_carteles lc
            JOIN dim_catalogo_codigo_identificacion_producto c
                ON lc.cod_producto = c.cod_producto
            CROSS JOIN periodo p
            WHERE c.nombre_segmento = :segmento
              AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
        ),
        adjudicadas_seg AS (
            SELECT la.monto_adjudicado_linea, la.nro_sicop
            FROM lineas_adjudicadas la
            JOIN carteles_seg cs
                ON la.nro_sicop = cs.nro_sicop AND la.nro_linea = cs.nro_linea
        ),
        ofertas_seg AS (
            SELECT lo.cedula_proveedor, lo.nro_sicop_nro_linea
            FROM lineas_ofertas lo
            JOIN carteles_seg cs
                ON lo.nro_sicop = cs.nro_sicop AND lo.nro_linea = cs.nro_linea
        )
        SELECT
            (SELECT COUNT(DISTINCT nro_sicop) FROM carteles_seg) AS carteles_publicados,
            (SELECT COALESCE(SUM(monto_adjudicado_linea), 0) FROM adjudicadas_seg)
                AS monto_adjudicado_total,
            (SELECT COUNT(DISTINCT cedula_proveedor) FROM ofertas_seg)
                AS proveedores_distintos,
            (SELECT CASE
                        WHEN COUNT(DISTINCT nro_sicop_nro_linea) = 0 THEN 0
                        ELSE COUNT(*)::numeric / COUNT(DISTINCT nro_sicop_nro_linea)
                    END
             FROM ofertas_seg) AS promedio_ofertas_por_linea;
    """)
    with _engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"segmento": segmento, "meses": int(meses)})
    return df.iloc[0]


@st.cache_data(ttl=600)
def get_instituciones_activas(_engine: Engine, segmento: str, meses: int) -> pd.DataFrame:
    """Top 20 instituciones con más carteles publicados en el segmento."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        )
        SELECT i.nombre_institucion,
               COUNT(DISTINCT lc.nro_sicop) AS carteles_publicados
        FROM lineas_carteles lc
        JOIN dim_instituciones i
            ON lc.cedula_institucion = i.cedula_institucion
        JOIN dim_catalogo_codigo_identificacion_producto c
            ON lc.cod_producto = c.cod_producto
        CROSS JOIN periodo p
        WHERE c.nombre_segmento = :segmento
          AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
        GROUP BY i.nombre_institucion
        ORDER BY carteles_publicados DESC
        LIMIT 20;
    """)
    with _engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"segmento": segmento, "meses": int(meses)})


@st.cache_data(ttl=600)
def get_ranking_proveedores(_engine: Engine, segmento: str, meses: int) -> pd.DataFrame:
    """Ranking de proveedores por monto adjudicado dentro del segmento."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        ),
        carteles_seg AS (
            SELECT lc.nro_sicop, lc.nro_linea
            FROM lineas_carteles lc
            JOIN dim_catalogo_codigo_identificacion_producto c
                ON lc.cod_producto = c.cod_producto
            CROSS JOIN periodo p
            WHERE c.nombre_segmento = :segmento
              AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
        )
        SELECT p.nombre_proveedor,
               COUNT(DISTINCT la.nro_sicop) AS carteles_ganados,
               SUM(la.monto_adjudicado_linea) AS monto_total_adjudicado
        FROM lineas_adjudicadas la
        JOIN carteles_seg cs
            ON la.nro_sicop = cs.nro_sicop AND la.nro_linea = cs.nro_linea
        JOIN dim_proveedores p
            ON la.cedula_proveedor = p.cedula_proveedor
        GROUP BY p.nombre_proveedor
        ORDER BY monto_total_adjudicado DESC
        LIMIT 15;
    """)
    with _engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"segmento": segmento, "meses": int(meses)})


@st.cache_data(ttl=600)
def get_evolucion_mensual(_engine: Engine, segmento: str, meses: int) -> pd.DataFrame:
    """Carteles publicados vs. adjudicados por mes, dentro del segmento."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        )
        SELECT DATE_TRUNC('month', lc.fecha_publicacion) AS mes,
               COUNT(DISTINCT lc.nro_sicop) AS cantidad,
               'Publicados' AS tipo
        FROM lineas_carteles lc
        JOIN dim_catalogo_codigo_identificacion_producto c
            ON lc.cod_producto = c.cod_producto
        CROSS JOIN periodo p
        WHERE c.nombre_segmento = :segmento
          AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
        GROUP BY 1

        UNION ALL

        SELECT DATE_TRUNC('month', la.fecha_adjud_firme) AS mes,
               COUNT(DISTINCT la.nro_sicop) AS cantidad,
               'Adjudicados' AS tipo
        FROM lineas_adjudicadas la
        JOIN dim_catalogo_codigo_identificacion_producto c
            ON la.cod_producto = c.cod_producto
        CROSS JOIN periodo p
        WHERE c.nombre_segmento = :segmento
          AND la.fecha_adjud_firme >= (p.max_fecha - make_interval(months => :meses))::date
        GROUP BY 1

        ORDER BY mes;
    """)
    with _engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"segmento": segmento, "meses": int(meses)})


@st.cache_data(ttl=600)
def get_detalle_carteles(_engine: Engine, segmento: str, meses: int, limite: int = 30) -> pd.DataFrame:
    """Últimos carteles del segmento: lo que el proveedor consulta para
    decidir si oferta o no."""
    query = text("""
        SELECT * FROM (
            SELECT DISTINCT ON (lc.nro_sicop)
                   lc.nro_sicop,
                   lc.nombre_cartel,
                   i.nombre_institucion,
                   lc.fecha_publicacion,
                   lc.fecha_apertura,
                   lc.monto_estimado_cartel_crc,
                   lc.status_cartel
            FROM lineas_carteles lc
            JOIN dim_instituciones i
                ON lc.cedula_institucion = i.cedula_institucion
            JOIN dim_catalogo_codigo_identificacion_producto c
                ON lc.cod_producto = c.cod_producto
            CROSS JOIN (
                SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
            ) p
            WHERE c.nombre_segmento = :segmento
              AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
            ORDER BY lc.nro_sicop, lc.fecha_publicacion DESC
        ) sub
        ORDER BY fecha_publicacion DESC
        LIMIT :limite;
    """)
    with _engine.connect() as conn:
        return pd.read_sql_query(
            query, conn, params={"segmento": segmento, "meses": int(meses), "limite": int(limite)}
        )


# ------------------------------------------------------------------
# Interfaz
# ------------------------------------------------------------------

st.title("SICOP - Carteles por segmento de producto")
st.caption(
    "Prototipo del TFM (Grupo 2, Máster en Big Data & BI). "
    "Ayuda a un proveedor MIPYME a evaluar los carteles de su segmento: "
    "quién compra, cuánto se adjudica y cuánta competencia existe."
)

try:
    engine = get_engine()
    periodo_max = get_periodo_referencia(engine)
except Exception as error:
    # Streamlit no siempre levanta KeyError cuando falta secrets.toml (a veces
    # es una excepción propia), así que se distingue por el mensaje en vez del
    # tipo de excepción.
    mensaje = str(error).lower()
    if "secrets" in mensaje or "postgres" in mensaje:
        st.error(
            "No se encontró la configuración de conexión en `.streamlit/secrets.toml`. "
            "Revisa 'Instrucciones Streamlit local.txt' para crear el archivo."
        )
    else:
        st.error(
            "No se pudo conectar a PostgreSQL. Verifica que el servidor esté iniciado, "
            "que la base `proyecto_sicop_v1` exista y que las credenciales sean correctas.\n\n"
            f"Detalle técnico: {error}"
        )
    st.stop()

if periodo_max is None:
    st.warning("La tabla `lineas_carteles` está vacía. Ejecuta los Pasos 1 a 4 del pipeline ETL.")
    st.stop()

df_segmentos = get_segmentos(engine)
if df_segmentos.empty:
    st.warning(
        "No hay segmentos disponibles. Verifica que el Paso 4 "
        "(carga del catálogo de productos) se haya ejecutado."
    )
    st.stop()

col_filtro_1, col_filtro_2 = st.columns([2, 1])
with col_filtro_1:
    segmento = st.selectbox(
        "Segmento de producto (clasificación UNSPSC de SICOP)",
        options=df_segmentos["nombre_segmento"],
        help="Ordenado por volumen de líneas de cartel publicadas, de mayor a menor.",
    )
with col_filtro_2:
    meses = st.slider(
        "Ventana de meses",
        min_value=1, max_value=24, value=12,
        help=f"Relativa al dato más reciente disponible ({periodo_max:%m/%Y}).",
    )

st.caption(f"Datos hasta {periodo_max:%d/%m/%Y}. Ventana activa: últimos {meses} meses.")

# --- KPIs ---
kpis = get_kpis(engine, segmento, meses)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Carteles publicados", f"{int(kpis['carteles_publicados']):,}".replace(",", "."))
k2.metric("Monto adjudicado", formatear_colones(kpis["monto_adjudicado_total"]))
k3.metric("Proveedores que ofertaron", f"{int(kpis['proveedores_distintos']):,}".replace(",", "."))
k4.metric("Ofertas promedio por línea", f"{kpis['promedio_ofertas_por_linea']:.1f}")

st.divider()

# --- Instituciones más activas ---
st.subheader(f"Instituciones más activas en «{segmento}»")
df_instituciones = get_instituciones_activas(engine, segmento, meses)

if df_instituciones.empty:
    st.info("No hay carteles publicados en este segmento durante la ventana seleccionada.")
else:
    grafico_instituciones = (
        alt.Chart(df_instituciones)
        .mark_bar()
        .encode(
            x=alt.X("carteles_publicados:Q", title="Cantidad de carteles"),
            y=alt.Y("nombre_institucion:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("nombre_institucion:N", title="Institución"),
                alt.Tooltip("carteles_publicados:Q", title="Carteles"),
            ],
        )
        .properties(height=500)
    )
    st.altair_chart(grafico_instituciones, width="stretch")

st.divider()

# --- Ranking de proveedores y evolución mensual ---
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("Ranking de proveedores por monto adjudicado")
    df_ranking = get_ranking_proveedores(engine, segmento, meses)
    if df_ranking.empty:
        st.info("Sin adjudicaciones registradas en este segmento y ventana.")
    else:
        df_ranking["monto_fmt"] = df_ranking["monto_total_adjudicado"].apply(formatear_colones)
        grafico_ranking = (
            alt.Chart(df_ranking)
            .mark_bar()
            .encode(
                x=alt.X("monto_total_adjudicado:Q", title="Monto adjudicado (CRC)"),
                y=alt.Y("nombre_proveedor:N", sort="-x", title=None),
                tooltip=[
                    alt.Tooltip("nombre_proveedor:N", title="Proveedor"),
                    alt.Tooltip("carteles_ganados:Q", title="Carteles ganados"),
                    alt.Tooltip("monto_fmt:N", title="Monto adjudicado"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(grafico_ranking, width="stretch")

with col_der:
    st.subheader("Carteles publicados vs. adjudicados por mes")
    df_evolucion = get_evolucion_mensual(engine, segmento, meses)
    if df_evolucion.empty:
        st.info("Sin datos suficientes para graficar la evolución mensual.")
    else:
        grafico_evolucion = (
            alt.Chart(df_evolucion)
            .mark_line(point=True)
            .encode(
                x=alt.X("mes:T", title="Mes"),
                y=alt.Y("cantidad:Q", title="Cantidad de carteles"),
                color=alt.Color("tipo:N", title=None),
                tooltip=[
                    alt.Tooltip("mes:T", title="Mes", format="%m/%Y"),
                    alt.Tooltip("tipo:N", title="Estado"),
                    alt.Tooltip("cantidad:Q", title="Cantidad"),
                ],
            )
            .properties(height=420)
        )
        st.altair_chart(grafico_evolucion, width="stretch")

st.divider()

# --- Detalle de carteles ---
st.subheader(f"Últimos carteles publicados en «{segmento}»")
df_detalle = get_detalle_carteles(engine, segmento, meses)

if df_detalle.empty:
    st.info("No hay carteles para mostrar con los filtros actuales.")
else:
    df_detalle_mostrar = df_detalle.copy()
    df_detalle_mostrar["monto_estimado_cartel_crc"] = df_detalle_mostrar[
        "monto_estimado_cartel_crc"
    ].apply(formatear_colones)
    df_detalle_mostrar = df_detalle_mostrar.rename(columns={
        "nombre_cartel": "Cartel",
        "nombre_institucion": "Institución",
        "fecha_publicacion": "Publicación",
        "fecha_apertura": "Apertura de ofertas",
        "monto_estimado_cartel_crc": "Monto estimado",
        "status_cartel": "Estado",
    }).drop(columns=["nro_sicop"])
    st.dataframe(df_detalle_mostrar, width="stretch", hide_index=True)
