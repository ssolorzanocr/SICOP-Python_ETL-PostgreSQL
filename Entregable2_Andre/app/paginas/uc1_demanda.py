"""
UC1 — Comportamiento de la demanda institucional.

"Un proveedor MIPYME quiere descubrir y evaluar los carteles de su segmento de
producto": elige un segmento de la clasificación UNSPSC de SICOP y una ventana de
meses, y la página responde quién compra, cuánto se adjudica, a qué precio, en
cuánto tiempo y cuánta competencia existe.

Migrada de PostgreSQL (proyecto_sicop_v1) al esquema `final` de DuckDB. Cambios
de nombres respecto de la versión anterior: lineas_carteles -> fact_lineas_carteles
(nro_linea -> numero_linea, nombre_cartel -> cartel_nm, status_cartel -> cartel_stat),
fecha_adjud_firme -> fecha_adjudicacion, dim_catalogo... -> dim_productos.
"""

import altair as alt
import pandas as pd
import streamlit as st

import datos as d

d.verificar_conexion()

# Líneas de cartel del segmento dentro de la ventana. Se reutiliza en todas las
# consultas de la página; los parámetros son (segmento, meses).
LINEAS_SEG = """
    lineas_seg AS (
        SELECT c.*
        FROM final.fact_lineas_carteles c
        JOIN final.dim_productos p ON p.cod_producto = TRY_CAST(c.cod_producto AS BIGINT)
        WHERE p.nombre_segmento = ?
          AND c.fecha_publicacion >= (SELECT MAX(fecha_publicacion) FROM final.fact_lineas_carteles)
                                     - to_months(CAST(? AS INTEGER))
    )
"""


@st.cache_data(ttl=3600)
def kpis(segmento: str, meses: int):
    return d.consultar(f"""
        WITH {LINEAS_SEG},
        ofertas_seg AS (
            SELECT o.* FROM final.fact_lineas_ofertas o
            JOIN lineas_seg l ON l.nro_sicop = o.nro_sicop AND l.numero_linea = o.nro_linea
        ),
        adj_seg AS (
            SELECT a.* FROM final.fact_lineas_adjudicadas a
            JOIN lineas_seg l ON l.nro_sicop = a.nro_sicop AND l.numero_linea = a.nro_linea
        )
        SELECT
            (SELECT COUNT(DISTINCT nro_sicop) FROM lineas_seg) AS carteles,
            (SELECT SUM({d.a_crc('monto_adjudicado_linea', 'tipo_moneda', 'tipo_cambio_crc')})
               FROM adj_seg) AS monto_adjudicado_crc,
            (SELECT COUNT(DISTINCT cedula_proveedor) FROM ofertas_seg) AS proveedores,
            (SELECT COUNT(*) / NULLIF(COUNT(DISTINCT (nro_sicop, nro_linea)), 0)
               FROM ofertas_seg) AS ofertas_por_linea
    """, [segmento, meses]).iloc[0]


@st.cache_data(ttl=3600)
def precios(segmento: str, meses: int):
    """Mediana de la razón precio adjudicado (u ofertado) / precio estimado,
    línea a línea: compara productos distintos sin mezclar escalas."""
    est = d.a_crc("l.precio_unitario_estimado", "l.tipo_moneda", "l.tipo_cambio_crc")
    adj = d.a_crc("a.precio_unitario_adjudicado", "a.tipo_moneda", "a.tipo_cambio_crc")
    ofe = d.a_crc("o.precio_unitario_ofertado", "o.tipo_moneda", "o.tipo_cambio_crc")
    return d.consultar(f"""
        WITH {LINEAS_SEG},
        est AS (SELECT l.nro_sicop, l.numero_linea, {est} AS precio_est
                FROM lineas_seg l WHERE l.precio_unitario_estimado > 0),
        r_adj AS (SELECT {adj} / e.precio_est AS razon
                  FROM final.fact_lineas_adjudicadas a
                  JOIN est e ON e.nro_sicop = a.nro_sicop AND e.numero_linea = a.nro_linea
                  WHERE a.precio_unitario_adjudicado > 0),
        r_ofe AS (SELECT {ofe} / e.precio_est AS razon
                  FROM final.fact_lineas_ofertas o
                  JOIN est e ON e.nro_sicop = o.nro_sicop AND e.numero_linea = o.nro_linea
                  WHERE o.precio_unitario_ofertado > 0)
        SELECT (SELECT MEDIAN(razon) FROM r_adj) AS razon_adj,
               (SELECT MEDIAN(razon) FROM r_ofe) AS razon_ofe,
               (SELECT COUNT(razon) FROM r_adj) AS n_adj
    """, [segmento, meses]).iloc[0]


@st.cache_data(ttl=3600)
def tiempos(segmento: str, meses: int):
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT QUANTILE_CONT(dias, 0.5) AS mediana, QUANTILE_CONT(dias, 0.25) AS p25,
               QUANTILE_CONT(dias, 0.75) AS p75, COUNT(*) AS n
        FROM (SELECT a.fecha_adjudicacion - l.fecha_publicacion AS dias
              FROM final.fact_lineas_adjudicadas a
              JOIN lineas_seg l ON l.nro_sicop = a.nro_sicop AND l.numero_linea = a.nro_linea
              WHERE a.fecha_adjudicacion >= l.fecha_publicacion)
    """, [segmento, meses]).iloc[0]


@st.cache_data(ttl=3600)
def instituciones(segmento: str, meses: int):
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT i.nombre_institucion,
               COUNT(DISTINCT l.nro_sicop) AS carteles,
               MEDIAN(a.fecha_adjudicacion - l.fecha_publicacion) AS dias_mediana
        FROM lineas_seg l
        JOIN final.dim_instituciones i ON i.cedula = l.cedula_institucion
        LEFT JOIN final.fact_lineas_adjudicadas a
               ON a.nro_sicop = l.nro_sicop AND a.nro_linea = l.numero_linea
              AND a.fecha_adjudicacion >= l.fecha_publicacion
        GROUP BY 1 ORDER BY 2 DESC LIMIT 20
    """, [segmento, meses])


@st.cache_data(ttl=3600)
def ranking_proveedores(segmento: str, meses: int):
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT p.nombre_proveedor, p.tamano_proveedor,
               COUNT(DISTINCT a.nro_sicop) AS carteles_ganados,
               SUM({d.a_crc('a.monto_adjudicado_linea', 'a.tipo_moneda', 'a.tipo_cambio_crc')}) AS monto_crc
        FROM final.fact_lineas_adjudicadas a
        JOIN lineas_seg l ON l.nro_sicop = a.nro_sicop AND l.numero_linea = a.nro_linea
        JOIN final.dim_proveedores p ON p.cedula_proveedor = a.cedula_proveedor
        GROUP BY 1, 2 ORDER BY monto_crc DESC NULLS LAST LIMIT 15
    """, [segmento, meses])


@st.cache_data(ttl=3600)
def evolucion(segmento: str, meses: int):
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT DATE_TRUNC('month', fecha_publicacion) AS mes,
               COUNT(DISTINCT nro_sicop) AS cantidad, 'Publicados' AS tipo
        FROM lineas_seg GROUP BY 1
        UNION ALL
        SELECT DATE_TRUNC('month', a.fecha_adjudicacion), COUNT(DISTINCT a.nro_sicop), 'Adjudicados'
        FROM final.fact_lineas_adjudicadas a
        JOIN lineas_seg l ON l.nro_sicop = a.nro_sicop AND l.numero_linea = a.nro_linea
        GROUP BY 1
        ORDER BY mes
    """, [segmento, meses])


@st.cache_data(ttl=3600)
def precios_por_producto(segmento: str, meses: int):
    est = d.a_crc("l.precio_unitario_estimado", "l.tipo_moneda", "l.tipo_cambio_crc")
    adj = d.a_crc("a.precio_unitario_adjudicado", "a.tipo_moneda", "a.tipo_cambio_crc")
    ofe = d.a_crc("o.precio_unitario_ofertado", "o.tipo_moneda", "o.tipo_cambio_crc")
    return d.consultar(f"""
        WITH {LINEAS_SEG},
        e AS (SELECT l.cod_producto, COUNT(DISTINCT l.nro_sicop) AS carteles,
                     MEDIAN({est}) AS estimado
              FROM lineas_seg l WHERE l.precio_unitario_estimado > 0 GROUP BY 1),
        o AS (SELECT l.cod_producto, MEDIAN({ofe}) AS ofertado
              FROM final.fact_lineas_ofertas o
              JOIN lineas_seg l ON l.nro_sicop = o.nro_sicop AND l.numero_linea = o.nro_linea
              WHERE o.precio_unitario_ofertado > 0 GROUP BY 1),
        a AS (SELECT l.cod_producto, MEDIAN({adj}) AS adjudicado
              FROM final.fact_lineas_adjudicadas a
              JOIN lineas_seg l ON l.nro_sicop = a.nro_sicop AND l.numero_linea = a.nro_linea
              WHERE a.precio_unitario_adjudicado > 0 GROUP BY 1)
        SELECT COALESCE(p.descripcion_producto, e.cod_producto) AS producto,
               e.carteles, e.estimado, o.ofertado, a.adjudicado
        FROM e
        LEFT JOIN final.dim_productos p ON p.cod_producto = TRY_CAST(e.cod_producto AS BIGINT)
        LEFT JOIN o ON o.cod_producto = e.cod_producto
        LEFT JOIN a ON a.cod_producto = e.cod_producto
        ORDER BY e.carteles DESC LIMIT 15
    """, [segmento, meses])


@st.cache_data(ttl=3600)
def ultimos_carteles(segmento: str, meses: int):
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT l.cartel_nm AS cartel, i.nombre_institucion AS institucion,
               l.fecha_publicacion, l.fecha_apertura,
               {d.a_crc('l.monto_estimado_cartel', 'l.tipo_moneda', 'l.tipo_cambio_crc')} AS monto_estimado_crc,
               l.cartel_stat AS estado
        FROM lineas_seg l
        JOIN final.dim_instituciones i ON i.cedula = l.cedula_institucion
        QUALIFY ROW_NUMBER() OVER (PARTITION BY l.nro_sicop ORDER BY l.numero_linea) = 1
        ORDER BY l.fecha_publicacion DESC LIMIT 30
    """, [segmento, meses])


@st.cache_data(ttl=3600)
def monto_por_tamano(segmento: str, meses: int):
    """Reparto del monto adjudicado según el tamaño del proveedor ganador:
    ¿cuánto del segmento se llevan las MIPYMES?"""
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT p.tamano_proveedor AS tamano,
               SUM({d.a_crc('a.monto_adjudicado_linea', 'a.tipo_moneda', 'a.tipo_cambio_crc')}) AS monto_crc,
               COUNT(DISTINCT a.cedula_proveedor) AS proveedores
        FROM final.fact_lineas_adjudicadas a
        JOIN lineas_seg l ON l.nro_sicop = a.nro_sicop AND l.numero_linea = a.nro_linea
        JOIN final.dim_proveedores p ON p.cedula_proveedor = a.cedula_proveedor
        WHERE p.tamano_proveedor IN ('Microemprendedor', 'Pequeña', 'Mediana', 'Grande')
        GROUP BY 1
    """, [segmento, meses])


@st.cache_data(ttl=3600)
def ofertas_por_linea(segmento: str, meses: int):
    """Cuántas líneas recibieron 1, 2, 3… ofertas (solo líneas con ofertas
    registradas). Es la distribución de la competencia que enfrentará el proveedor."""
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT LEAST(COUNT(*), 8) AS ofertas
        FROM final.fact_lineas_ofertas o
        JOIN lineas_seg l ON l.nro_sicop = o.nro_sicop AND l.numero_linea = o.nro_linea
        GROUP BY o.nro_sicop, o.nro_linea
    """, [segmento, meses]).groupby("ofertas").size().rename("lineas").reset_index()


@st.cache_data(ttl=3600)
def razones_precio(segmento: str, meses: int):
    """Razón precio adjudicado / precio estimado línea a línea, para ver la
    distribución completa (el KPI solo muestra la mediana)."""
    est = d.a_crc("l.precio_unitario_estimado", "l.tipo_moneda", "l.tipo_cambio_crc")
    adj = d.a_crc("a.precio_unitario_adjudicado", "a.tipo_moneda", "a.tipo_cambio_crc")
    return d.consultar(f"""
        WITH {LINEAS_SEG}
        SELECT ({adj}) / ({est}) AS razon
        FROM final.fact_lineas_adjudicadas a
        JOIN lineas_seg l ON l.nro_sicop = a.nro_sicop AND l.numero_linea = a.nro_linea
        WHERE l.precio_unitario_estimado > 0 AND a.precio_unitario_adjudicado > 0
    """, [segmento, meses]).dropna()


@st.cache_data(ttl=3600)
def posicion_precio_ganador(segmento: str, meses: int):
    """En las líneas con 2 o más ofertas con precio: ¿la ganadora era la más barata,
    la segunda…? Muestra cuánto pesa el precio frente a otros criterios de adjudicación."""
    ofe = d.a_crc("o.precio_unitario_ofertado", "o.tipo_moneda", "o.tipo_cambio_crc")
    return d.consultar(f"""
        WITH {LINEAS_SEG},
        ofertas AS (
            SELECT o.nro_sicop, o.nro_linea, o.cedula_proveedor, {ofe} AS precio
            FROM final.fact_lineas_ofertas o
            JOIN lineas_seg l ON l.nro_sicop = o.nro_sicop AND l.numero_linea = o.nro_linea
            WHERE o.precio_unitario_ofertado > 0
        ),
        ranking AS (
            SELECT *, RANK() OVER (PARTITION BY nro_sicop, nro_linea ORDER BY precio) AS posicion,
                   COUNT(*) OVER (PARTITION BY nro_sicop, nro_linea) AS n
            FROM ofertas WHERE precio IS NOT NULL
        )
        SELECT LEAST(r.posicion, 4) AS posicion, COUNT(*) AS lineas
        FROM ranking r
        JOIN (SELECT DISTINCT nro_sicop, nro_linea, cedula_proveedor
              FROM final.fact_lineas_adjudicadas) g USING (nro_sicop, nro_linea, cedula_proveedor)
        WHERE r.n >= 2
        GROUP BY 1 ORDER BY 1
    """, [segmento, meses])


# ------------------------------------------------------------------
# Interfaz
# ------------------------------------------------------------------

st.title("Demanda institucional por segmento")
st.caption("**Caso de uso 1.** ¿Quién compra lo que vendo, cuánto, a qué precio, en cuánto "
           "tiempo adjudica y cuánta competencia hay?")

f_max = d.fecha_maxima()
c1, c2 = st.columns([2, 1])
segmento = c1.selectbox("Segmento de producto (clasificación UNSPSC de SICOP)",
                        d.segmentos()["nombre_segmento"],
                        help="Ordenado por volumen de líneas publicadas.")
meses = c2.slider("Ventana de meses", 1, 24, 12, help=f"Relativa al dato más reciente ({f_max:%d/%m/%Y}).")
st.caption(f"Datos hasta {f_max:%d/%m/%Y} · últimos {meses} meses.")

k, pr, ti = kpis(segmento, meses), precios(segmento, meses), tiempos(segmento, meses)
m = st.columns(3) + st.columns(3)
m[0].metric("Carteles publicados", d.entero(k["carteles"]))
m[1].metric("Monto adjudicado", d.colones_compacto(k["monto_adjudicado_crc"]),
            help=f"{d.colones(k['monto_adjudicado_crc'])}. Suma de las líneas adjudicadas, "
                 "convertida a colones (USD × tipo de cambio).")
m[2].metric("Proveedores que ofertaron", d.entero(k["proveedores"]))
m[3].metric("Ofertas por línea", "s/d" if k["ofertas_por_linea"] is None else
            f"{k['ofertas_por_linea']:.1f}".replace(".", ","),
            help="Promedio sobre las líneas que tienen ofertas registradas.")
m[4].metric("Adjudicado vs. estimado", d.variacion(pr["razon_adj"]),
            help=f"Mediana de la razón precio adjudicado / estimado, línea a línea "
                 f"({d.entero(pr['n_adj'])} líneas). Ofertado vs. estimado: {d.variacion(pr['razon_ofe'])}.")
m[5].metric("Días hasta adjudicar", d.dias(ti["mediana"]),
            help=f"Mediana desde la publicación. P25–P75: {d.dias(ti['p25'])} – {d.dias(ti['p75'])}.")

st.divider()
st.subheader("Instituciones que más compran en este segmento")
df_i = instituciones(segmento, meses)
if df_i.empty:
    st.info("No hay carteles en este segmento y ventana.")
else:
    df_i["dias_fmt"] = df_i["dias_mediana"].apply(d.dias)
    st.altair_chart(
        alt.Chart(df_i).mark_bar(color=d.SERIE[0], cornerRadiusEnd=4, height={"band": 0.7})
        .encode(x=alt.X("carteles:Q", title="Carteles publicados"),
                y=alt.Y("nombre_institucion:N", sort="-x", title=None, axis=alt.Axis(labelLimit=360)),
                tooltip=[alt.Tooltip("nombre_institucion:N", title="Institución"),
                         alt.Tooltip("carteles:Q", title="Carteles"),
                         alt.Tooltip("dias_fmt:N", title="Días hasta adjudicar (mediana)")])
        .properties(height=480),
        width="stretch")

st.divider()
izq, der = st.columns(2)
with izq:
    st.subheader("Quién gana: proveedores por monto adjudicado")
    df_r = ranking_proveedores(segmento, meses)
    if df_r.empty:
        st.info("Sin adjudicaciones en este segmento y ventana.")
    else:
        df_r["monto_fmt"] = df_r["monto_crc"].apply(d.colones)
        st.altair_chart(
            alt.Chart(df_r).mark_bar(color=d.SERIE[0], cornerRadiusEnd=4)
            .encode(x=alt.X("monto_crc:Q", title="Monto adjudicado (₡)"),
                    y=alt.Y("nombre_proveedor:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                    tooltip=[alt.Tooltip("nombre_proveedor:N", title="Proveedor"),
                             alt.Tooltip("tamano_proveedor:N", title="Tamaño"),
                             alt.Tooltip("carteles_ganados:Q", title="Carteles ganados"),
                             alt.Tooltip("monto_fmt:N", title="Monto")])
            .properties(height=420),
            width="stretch")
with der:
    st.subheader("Carteles publicados y adjudicados por mes")
    df_e = evolucion(segmento, meses)
    if df_e.empty:
        st.info("Sin datos para la evolución mensual.")
    else:
        st.altair_chart(
            alt.Chart(df_e).mark_line(point=alt.OverlayMarkDef(size=60), strokeWidth=2)
            .encode(x=alt.X("mes:T", title=None, axis=alt.Axis(format="%m/%Y")),
                    y=alt.Y("cantidad:Q", title="Carteles"),
                    color=alt.Color("tipo:N", title=None,
                                    scale=alt.Scale(domain=["Publicados", "Adjudicados"],
                                                    range=d.SERIE[:2]),
                                    legend=alt.Legend(orient="top")),
                    tooltip=[alt.Tooltip("mes:T", title="Mes", format="%m/%Y"),
                             alt.Tooltip("tipo:N", title="Estado"),
                             alt.Tooltip("cantidad:Q", title="Carteles")])
            .properties(height=420),
            width="stretch")

st.divider()
st.subheader("Competencia y precios en el segmento")
c_izq, c_der = st.columns(2)

with c_izq:
    st.markdown("**¿Cuántas ofertas recibe cada línea?**")
    df_o = ofertas_por_linea(segmento, meses)
    if df_o.empty:
        st.info("Sin ofertas registradas en este segmento y ventana.")
    else:
        df_o["etiqueta"] = df_o["ofertas"].map(lambda v: "8+" if v >= 8 else str(int(v)))
        df_o["pct"] = df_o["lineas"] / df_o["lineas"].sum()
        st.altair_chart(
            alt.Chart(df_o).mark_bar(color=d.SERIE[0], cornerRadiusEnd=4)
            .encode(x=alt.X("etiqueta:O", sort=None, title="Ofertas en la línea", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("lineas:Q", title="Líneas"),
                    tooltip=[alt.Tooltip("etiqueta:N", title="Ofertas"),
                             alt.Tooltip("lineas:Q", title="Líneas", format=",.0f"),
                             alt.Tooltip("pct:Q", title="% de líneas", format=".0%")])
            .properties(height=260),
            width="stretch")
        st.caption(f"En el {d.porcentaje(df_o.loc[df_o['ofertas'] == 1, 'pct'].sum())} de las "
                   "líneas hubo una sola oferta: ahí no compitió nadie más.")

with c_der:
    st.markdown("**¿Gana siempre la oferta más barata?**")
    df_pos = posicion_precio_ganador(segmento, meses)
    if df_pos.empty:
        st.info("No hay líneas con 2 o más ofertas con precio en este segmento y ventana.")
    else:
        nombres_pos = {1: "La más barata", 2: "2.ª más barata", 3: "3.ª más barata", 4: "4.ª o más cara"}
        df_pos["posicion_txt"] = df_pos["posicion"].map(nombres_pos)
        df_pos["pct"] = df_pos["lineas"] / df_pos["lineas"].sum()
        st.altair_chart(
            alt.Chart(df_pos).mark_bar(color=d.SERIE[0], cornerRadiusEnd=4)
            .encode(y=alt.Y("posicion_txt:N", sort=list(nombres_pos.values()), title=None),
                    x=alt.X("pct:Q", title="Líneas adjudicadas", axis=alt.Axis(format="%"),
                            scale=alt.Scale(domain=[0, 1])),
                    tooltip=[alt.Tooltip("posicion_txt:N", title="Oferta ganadora"),
                             alt.Tooltip("lineas:Q", title="Líneas", format=",.0f"),
                             alt.Tooltip("pct:Q", title="%", format=".0%")])
            .properties(height=260),
            width="stretch")
        st.caption("Posición en precio de la oferta adjudicada. Lo que no es «la más barata» "
                   "se adjudicó por otros criterios (técnicos, criterio PYME, etc.).")

c_izq, c_der = st.columns(2)
with c_izq:
    st.markdown("**Precio adjudicado frente al estimado del cartel**")
    df_rz = razones_precio(segmento, meses)
    if df_rz.empty:
        st.info("Sin líneas adjudicadas con precio estimado en este segmento y ventana.")
    else:
        # Se recorta a [0; 2] para que unos pocos errores de unidad no aplasten el gráfico.
        df_rz["variacion"] = df_rz["razon"].clip(0, 2) - 1
        base = alt.Chart(df_rz)
        barras = base.mark_bar(color=d.SERIE[0]).encode(
            x=alt.X("variacion:Q", bin=alt.Bin(step=0.1, extent=[-1, 1]),
                    title="Adjudicado vs. estimado", axis=alt.Axis(format="+%")),
            y=alt.Y("count():Q", title="Líneas"),
            tooltip=[alt.Tooltip("variacion:Q", bin=alt.Bin(step=0.1, extent=[-1, 1]),
                                 title="Variación", format="+.0%"),
                     alt.Tooltip("count():Q", title="Líneas")])
        cero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[4, 4], color="#898781") \
            .encode(x="x:Q")
        st.altair_chart((barras + cero).properties(height=260), width="stretch")
        st.caption("A la izquierda de la línea punteada, el contrato se cerró por debajo del "
                   "presupuesto estimado: margen de negociación en precio.")

with c_der:
    st.markdown("**¿Quién se lleva el monto? Por tamaño de proveedor**")
    df_t = monto_por_tamano(segmento, meses)
    if df_t.empty:
        st.info("Sin adjudicaciones en este segmento y ventana.")
    else:
        orden_tam = ["Microemprendedor", "Pequeña", "Mediana", "Grande"]
        df_t["pct"] = df_t["monto_crc"] / df_t["monto_crc"].sum()
        df_t["monto_fmt"] = df_t["monto_crc"].apply(d.colones)
        st.altair_chart(
            alt.Chart(df_t).mark_bar(cornerRadiusEnd=4)
            .encode(y=alt.Y("tamano:N", sort=orden_tam, title=None),
                    x=alt.X("pct:Q", title="% del monto adjudicado", axis=alt.Axis(format="%"),
                            scale=alt.Scale(domain=[0, 1])),
                    color=alt.Color("tamano:N", scale=alt.Scale(domain=orden_tam, range=d.SERIE),
                                    legend=None),
                    tooltip=[alt.Tooltip("tamano:N", title="Tamaño"),
                             alt.Tooltip("pct:Q", title="% del monto", format=".0%"),
                             alt.Tooltip("monto_fmt:N", title="Monto"),
                             alt.Tooltip("proveedores:Q", title="Proveedores ganadores")])
            .properties(height=260),
            width="stretch")
        mipyme = df_t.loc[df_t["tamano"] != "Grande", "pct"].sum()
        st.caption(f"Las MIPYMES (micro, pequeñas y medianas) se llevan el "
                   f"{d.porcentaje(mipyme)} del monto adjudicado en este segmento.")

st.divider()
st.subheader("Precios por producto (mediana, en colones)")
df_p = precios_por_producto(segmento, meses)
if df_p.empty:
    st.info("No hay líneas con precio estimado en este segmento y ventana.")
else:
    df_p["Adjudicado vs. estimado"] = (df_p["adjudicado"] / df_p["estimado"]).apply(d.variacion)
    for col in ("estimado", "ofertado", "adjudicado"):
        df_p[col] = df_p[col].apply(d.colones)
    st.dataframe(df_p.rename(columns={"producto": "Producto", "carteles": "Carteles",
                                      "estimado": "Estimado", "ofertado": "Ofertado",
                                      "adjudicado": "Adjudicado"}),
                 hide_index=True, width="stretch")

st.subheader("Últimos carteles publicados")
df_u = ultimos_carteles(segmento, meses)
df_u["monto_estimado_crc"] = df_u["monto_estimado_crc"].apply(d.colones)
st.dataframe(df_u.rename(columns={"cartel": "Cartel", "institucion": "Institución",
                                  "fecha_publicacion": "Publicación", "fecha_apertura": "Apertura",
                                  "monto_estimado_crc": "Monto estimado", "estado": "Estado"}),
             hide_index=True, width="stretch")

st.caption("**Notas.** Montos y precios convertidos a colones: CRC tal cual, USD × tipo de cambio "
           "registrado; otras monedas (<1 % de las líneas) se excluyen de los indicadores de precio. "
           "En la versión actual de los datos, la tabla de ofertas cubre solo parte de los "
           "procedimientos publicados: «Proveedores que ofertaron» y «Ofertas por línea» describen "
           "los procedimientos con ofertas registradas.")
