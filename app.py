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
    """Top 20 instituciones con más carteles publicados en el segmento, con la
    mediana de días entre publicación y adjudicación firme de cada una
    (NULL si la institución no tiene adjudicaciones en la ventana)."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        )
        SELECT i.nombre_institucion,
               COUNT(DISTINCT lc.nro_sicop) AS carteles_publicados,
               PERCENTILE_CONT(0.5) WITHIN GROUP (
                   ORDER BY (la.fecha_adjud_firme - lc.fecha_publicacion::date)
               ) AS dias_mediana_adjudicacion
        FROM lineas_carteles lc
        JOIN dim_instituciones i
            ON lc.cedula_institucion = i.cedula_institucion
        JOIN dim_catalogo_codigo_identificacion_producto c
            ON lc.cod_producto = c.cod_producto
        LEFT JOIN lineas_adjudicadas la
            ON la.nro_sicop = lc.nro_sicop AND la.nro_linea = lc.nro_linea
           AND la.fecha_adjud_firme >= lc.fecha_publicacion::date
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
# Precios y tiempos (UC1: comportamiento de la demanda institucional)
#
# Conversión de moneda: el pipeline ETL carga los precios unitarios en la
# moneda original, con tipo_moneda y tipo_cambio_crc al lado. Cada consulta
# los lleva a colones con la misma regla:
#     tipo_moneda = 'CRC'  -> el precio tal cual
#     tipo_cambio_crc > 0  -> precio * tipo_cambio_crc
#     en otro caso         -> NULL (se excluye; mejor sin dato que un dato mal)
# TODO: confirmar contra la base real el valor literal de tipo_moneda para
# colones ('CRC') y la semántica de tipo_cambio_crc. Ver plan, sección 2.
# ------------------------------------------------------------------

@st.cache_data(ttl=600)
def get_precios(_engine: Engine, segmento: str, meses: int) -> pd.Series:
    """Relación entre el precio unitario adjudicado (y ofertado) y el precio
    estimado del cartel, como mediana de la razón línea a línea.

    Los precios absolutos no se comparan entre productos distintos del mismo
    segmento; la razón sí: una mediana de 0,88 significa que la mitad de las
    adjudicaciones cerraron un 12 % o más por debajo del estimado."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        ),
        carteles_seg AS (
            SELECT lc.nro_sicop, lc.nro_linea,
                   CASE
                       WHEN lc.tipo_moneda = 'CRC' THEN lc.precio_unitario_estimado
                       WHEN lc.tipo_cambio_crc > 0
                            THEN lc.precio_unitario_estimado * lc.tipo_cambio_crc
                   END AS precio_est_crc
            FROM lineas_carteles lc
            JOIN dim_catalogo_codigo_identificacion_producto c
                ON lc.cod_producto = c.cod_producto
            CROSS JOIN periodo p
            WHERE c.nombre_segmento = :segmento
              AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
              AND lc.precio_unitario_estimado > 0
        ),
        razon_adj AS (
            SELECT (CASE
                        WHEN la.moneda_adjudicada = 'CRC' THEN la.precio_unitario_adjudicado
                        WHEN la.tipo_cambio_crc > 0
                             THEN la.precio_unitario_adjudicado * la.tipo_cambio_crc
                    END) / cs.precio_est_crc AS razon
            FROM lineas_adjudicadas la
            JOIN carteles_seg cs
                ON la.nro_sicop = cs.nro_sicop AND la.nro_linea = cs.nro_linea
            WHERE la.precio_unitario_adjudicado > 0
              AND cs.precio_est_crc > 0
        ),
        razon_of AS (
            SELECT (CASE
                        WHEN lo.tipo_moneda = 'CRC' THEN lo.precio_unitario_ofertado
                        WHEN lo.tipo_cambio_crc > 0
                             THEN lo.precio_unitario_ofertado * lo.tipo_cambio_crc
                    END) / cs.precio_est_crc AS razon
            FROM lineas_ofertas lo
            JOIN carteles_seg cs
                ON lo.nro_sicop = cs.nro_sicop AND lo.nro_linea = cs.nro_linea
            WHERE lo.precio_unitario_ofertado > 0
              AND cs.precio_est_crc > 0
        )
        SELECT
            (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY razon)
             FROM razon_adj WHERE razon IS NOT NULL) AS razon_adj_est_mediana,
            (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY razon)
             FROM razon_of WHERE razon IS NOT NULL)  AS razon_of_est_mediana,
            (SELECT COUNT(*) FROM razon_adj WHERE razon IS NOT NULL)
                AS lineas_adjudicadas_con_precio,
            (SELECT COUNT(*) FROM razon_of WHERE razon IS NOT NULL)
                AS lineas_ofertadas_con_precio;
    """)
    with _engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"segmento": segmento, "meses": int(meses)})
    return df.iloc[0]


@st.cache_data(ttl=600)
def get_precios_por_producto(_engine: Engine, segmento: str, meses: int,
                             limite: int = 15) -> pd.DataFrame:
    """Para los productos más demandados del segmento, la mediana del precio
    unitario estimado, ofertado y adjudicado, todo en colones. Cada mediana
    se calcula por separado para que la cantidad de ofertas de una línea no
    pese sobre el estimado ni sobre el adjudicado."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        ),
        lineas_seg AS (
            SELECT lc.nro_sicop, lc.nro_linea, lc.cod_producto,
                   CASE
                       WHEN lc.tipo_moneda = 'CRC' THEN lc.precio_unitario_estimado
                       WHEN lc.tipo_cambio_crc > 0
                            THEN lc.precio_unitario_estimado * lc.tipo_cambio_crc
                   END AS precio_est_crc
            FROM lineas_carteles lc
            JOIN dim_catalogo_codigo_identificacion_producto c
                ON lc.cod_producto = c.cod_producto
            CROSS JOIN periodo p
            WHERE c.nombre_segmento = :segmento
              AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
        ),
        est AS (
            SELECT cod_producto,
                   COUNT(DISTINCT nro_sicop) AS carteles,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio_est_crc)
                       AS precio_estimado_mediana
            FROM lineas_seg
            WHERE precio_est_crc > 0
            GROUP BY cod_producto
        ),
        ofe AS (
            SELECT ls.cod_producto,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
                       CASE
                           WHEN lo.tipo_moneda = 'CRC' THEN lo.precio_unitario_ofertado
                           WHEN lo.tipo_cambio_crc > 0
                                THEN lo.precio_unitario_ofertado * lo.tipo_cambio_crc
                       END) AS precio_ofertado_mediana
            FROM lineas_ofertas lo
            JOIN lineas_seg ls
                ON lo.nro_sicop = ls.nro_sicop AND lo.nro_linea = ls.nro_linea
            WHERE lo.precio_unitario_ofertado > 0
            GROUP BY ls.cod_producto
        ),
        adj AS (
            SELECT ls.cod_producto,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
                       CASE
                           WHEN la.moneda_adjudicada = 'CRC' THEN la.precio_unitario_adjudicado
                           WHEN la.tipo_cambio_crc > 0
                                THEN la.precio_unitario_adjudicado * la.tipo_cambio_crc
                       END) AS precio_adjudicado_mediana
            FROM lineas_adjudicadas la
            JOIN lineas_seg ls
                ON la.nro_sicop = ls.nro_sicop AND la.nro_linea = ls.nro_linea
            WHERE la.precio_unitario_adjudicado > 0
            GROUP BY ls.cod_producto
        )
        SELECT c.cod_producto,
               COALESCE(c.descripcion_producto, c.nombre_mercancia,
                        c.cod_producto::text) AS producto,
               est.carteles,
               est.precio_estimado_mediana,
               ofe.precio_ofertado_mediana,
               adj.precio_adjudicado_mediana
        FROM est
        JOIN dim_catalogo_codigo_identificacion_producto c
            ON est.cod_producto = c.cod_producto
        LEFT JOIN ofe ON ofe.cod_producto = est.cod_producto
        LEFT JOIN adj ON adj.cod_producto = est.cod_producto
        ORDER BY est.carteles DESC, c.cod_producto
        LIMIT :limite;
    """)
    with _engine.connect() as conn:
        return pd.read_sql_query(
            query, conn, params={"segmento": segmento, "meses": int(meses), "limite": int(limite)}
        )


@st.cache_data(ttl=600)
def get_tiempos(_engine: Engine, segmento: str, meses: int) -> pd.Series:
    """Días entre la publicación del cartel y la adjudicación firme de sus
    líneas, en el segmento y la ventana: mediana, P25, P75 y cantidad de
    líneas consideradas.

    Nota: la Asignatura 5 midió DIAS_PARA_ADJUDICACION desde la fecha de
    solicitud de contratación (media 167,66; mediana 146). Aquí se mide desde
    fecha_publicacion, que es la que tiene el modelo dimensional."""
    query = text("""
        WITH periodo AS (
            SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
        ),
        tiempos AS (
            SELECT (la.fecha_adjud_firme - lc.fecha_publicacion::date) AS dias
            FROM lineas_adjudicadas la
            JOIN lineas_carteles lc
                ON la.nro_sicop = lc.nro_sicop AND la.nro_linea = lc.nro_linea
            JOIN dim_catalogo_codigo_identificacion_producto c
                ON lc.cod_producto = c.cod_producto
            CROSS JOIN periodo p
            WHERE c.nombre_segmento = :segmento
              AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => :meses)
              AND la.fecha_adjud_firme IS NOT NULL
              AND la.fecha_adjud_firme >= lc.fecha_publicacion::date
        )
        SELECT
            PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY dias) AS dias_mediana,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY dias) AS dias_p25,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY dias) AS dias_p75,
            COUNT(*) AS lineas_adjudicadas
        FROM tiempos;
    """)
    with _engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"segmento": segmento, "meses": int(meses)})
    return df.iloc[0]


# ------------------------------------------------------------------
# Interfaz
# ------------------------------------------------------------------

st.title("SICOP - Carteles por segmento de producto")
st.caption(
    "Prototipo del TFM (Grupo 2, Máster en Big Data & BI) — "
    "**Caso de uso 1: comportamiento de la demanda institucional.** "
    "Ayuda a un proveedor MIPYME a evaluar los carteles de su segmento: "
    "quién compra, cuánto se adjudica, a qué precio, en cuánto tiempo y "
    "cuánta competencia existe."
)


def formatear_porcentaje_razon(razon) -> str:
    """Convierte una razón (adjudicado/estimado) en variación porcentual:
    0,88 -> '-12,0 %'; 1,05 -> '+5,0 %'. 's/d' si no hay dato."""
    if razon is None or pd.isna(razon):
        return "s/d"
    return f"{(float(razon) - 1) * 100:+.1f} %".replace(".", ",")


def formatear_dias(valor) -> str:
    if valor is None or pd.isna(valor):
        return "s/d"
    return f"{float(valor):.0f} días"

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
precios = get_precios(engine, segmento, meses)
tiempos = get_tiempos(engine, segmento, meses)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Carteles publicados", f"{int(kpis['carteles_publicados']):,}".replace(",", "."))
k2.metric("Monto adjudicado", formatear_colones(kpis["monto_adjudicado_total"]))
k3.metric("Proveedores que ofertaron", f"{int(kpis['proveedores_distintos']):,}".replace(",", "."))
k4.metric("Ofertas promedio por línea", f"{kpis['promedio_ofertas_por_linea']:.1f}")
k5.metric(
    "Precio adjudicado vs. estimado",
    formatear_porcentaje_razon(precios["razon_adj_est_mediana"]),
    help=(
        "Mediana de la razón precio adjudicado / precio estimado del cartel, "
        "línea a línea. Un valor negativo indica que las adjudicaciones cierran "
        "por debajo del estimado. Precio ofertado vs. estimado: "
        f"{formatear_porcentaje_razon(precios['razon_of_est_mediana'])} "
        f"({int(precios['lineas_adjudicadas_con_precio'])} líneas adjudicadas con precio)."
    ),
)
k6.metric(
    "Días hasta adjudicación",
    formatear_dias(tiempos["dias_mediana"]),
    help=(
        "Mediana de días entre la publicación del cartel y la adjudicación firme. "
        f"Rango P25–P75: {formatear_dias(tiempos['dias_p25'])} – "
        f"{formatear_dias(tiempos['dias_p75'])} "
        f"({int(tiempos['lineas_adjudicadas'])} líneas)."
    ),
)

st.divider()

# --- Instituciones más activas ---
st.subheader(f"Instituciones más activas en «{segmento}»")
df_instituciones = get_instituciones_activas(engine, segmento, meses)

if df_instituciones.empty:
    st.info("No hay carteles publicados en este segmento durante la ventana seleccionada.")
else:
    df_instituciones["dias_fmt"] = df_instituciones["dias_mediana_adjudicacion"].apply(
        formatear_dias
    )
    grafico_instituciones = (
        alt.Chart(df_instituciones)
        .mark_bar()
        .encode(
            x=alt.X("carteles_publicados:Q", title="Cantidad de carteles"),
            y=alt.Y("nombre_institucion:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("nombre_institucion:N", title="Institución"),
                alt.Tooltip("carteles_publicados:Q", title="Carteles"),
                alt.Tooltip("dias_fmt:N", title="Días hasta adjudicación (mediana)"),
            ],
        )
        .properties(height=500)
    )
    st.altair_chart(grafico_instituciones, width="stretch")
    st.caption(
        "Pasa el cursor sobre una barra para ver cuántos días tarda esa institución, "
        "en mediana, entre publicar y adjudicar en firme."
    )

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

# --- Precios por producto ---
st.subheader(f"Precios por producto en «{segmento}»")
st.caption(
    "Los productos más demandados del segmento y la mediana de su precio unitario "
    "estimado en el cartel, ofertado por los proveedores y finalmente adjudicado. "
    "Todos los montos en colones."
)
df_precios = get_precios_por_producto(engine, segmento, meses)

if df_precios.empty:
    st.info("No hay líneas con precio estimado en este segmento y ventana.")
else:
    df_precios_mostrar = df_precios.copy()
    df_precios_mostrar["variacion"] = (
        df_precios_mostrar["precio_adjudicado_mediana"]
        / df_precios_mostrar["precio_estimado_mediana"]
    ).apply(formatear_porcentaje_razon)
    for col in ("precio_estimado_mediana", "precio_ofertado_mediana", "precio_adjudicado_mediana"):
        df_precios_mostrar[col] = df_precios_mostrar[col].apply(formatear_colones)
    df_precios_mostrar = df_precios_mostrar.rename(columns={
        "producto": "Producto",
        "carteles": "Carteles",
        "precio_estimado_mediana": "Estimado (mediana)",
        "precio_ofertado_mediana": "Ofertado (mediana)",
        "precio_adjudicado_mediana": "Adjudicado (mediana)",
        "variacion": "Adjudicado vs. estimado",
    }).drop(columns=["cod_producto"])
    st.dataframe(df_precios_mostrar, width="stretch", hide_index=True)

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

st.divider()
st.caption(
    "**Nota sobre monedas.** Los precios unitarios se registran en SICOP en la moneda "
    "de cada cartel u oferta. Para compararlos, la aplicación los convierte a colones con "
    "el tipo de cambio registrado en cada línea (`tipo_cambio_crc`); las líneas en otra "
    "moneda sin tipo de cambio se excluyen de los indicadores de precio. "
    "Los días hasta adjudicación se miden desde la fecha de publicación del cartel."
)
