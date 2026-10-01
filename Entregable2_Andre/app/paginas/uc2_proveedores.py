"""
UC2 — Caracterización de proveedores.

Usa la segmentación KMeans de la Asignatura 7 (notebooks/clustering_proveedores.ipynb):
cada proveedor con historial suficiente pertenece a uno de cuatro perfiles de
comportamiento. La página permite:
  1. ver los cuatro perfiles del mercado (benchmarking general);
  2. buscar un proveedor y compararlo con la mediana de su perfil;
  3. ver el mapa de oportunidades por segmento (hipótesis 3 del TFM).
"""

import altair as alt
import pandas as pd
import streamlit as st

import datos as d

d.verificar_conexion()

PERFILES = ["Generalistas de alto volumen", "Competidores focalizados",
            "Nicho con poca competencia", "Sin adjudicaciones"]
DESCRIPCION = {
    "Generalistas de alto volumen": "Ofertan mucho, en muchos segmentos e instituciones. "
                                    "Ganan alrededor de 1 de cada 3 líneas.",
    "Competidores focalizados": "Pocos segmentos, varios competidores por línea. "
                                "Contratos de mayor tamaño; ganan ~1 de cada 4 líneas.",
    "Nicho con poca competencia": "Pocos segmentos y casi sin competidores: ganan la mayoría "
                                  "de lo que ofertan.",
    "Sin adjudicaciones": "Ofertan en líneas muy disputadas y aún no ganan. "
                          "Perfil típico de quien necesita información para elegir mejor.",
}

seg = d.leer_parquet("segmentos_proveedores.parquet")
mapa = d.leer_parquet("mapa_oportunidades.parquet")
if seg is None:
    st.error("Falta `app/datos/segmentos_proveedores.parquet`. Ejecuta el cuaderno "
             "`notebooks/clustering_proveedores.ipynb` para generarlo.")
    st.stop()


@st.cache_data(ttl=3600)
def nombres() -> pd.DataFrame:
    return d.consultar("SELECT cedula_proveedor, nombre_proveedor FROM final.dim_proveedores")


seg = seg.merge(nombres(), on="cedula_proveedor", how="left")
medianas = seg.groupby("segmento_proveedor")[
    ["lineas_ofertadas", "segmentos", "instituciones", "tasa_exito",
     "competidores_promedio", "ticket"]].median()

st.title("Caracterización de proveedores")
st.caption("**Caso de uso 2.** ¿Contra quién compito, a qué tipo de proveedor me parezco y "
           "qué hacen los que ganan?")

# --- 1. Perfiles del mercado ---
st.subheader("Los cuatro perfiles de proveedor")
cols = st.columns(4)
for col, perfil in zip(cols, PERFILES):
    sub = seg[seg["segmento_proveedor"] == perfil]
    with col.container(border=True):
        st.markdown(f"**{perfil}**")
        st.caption(DESCRIPCION[perfil])
        st.metric("Proveedores", d.entero(len(sub)))
        st.metric("Tasa de éxito (mediana)", d.porcentaje(sub["tasa_exito"].median()))
        st.metric("Competidores por línea", f"{sub['competidores_promedio'].median():.1f}".replace(".", ","))

tam = (seg[seg["tamano_proveedor"].isin(["Microemprendedor", "Pequeña", "Mediana", "Grande"])]
       .groupby(["segmento_proveedor", "tamano_proveedor"]).size().rename("n").reset_index())
st.altair_chart(
    alt.Chart(tam).mark_bar(stroke="#fcfcfb", strokeWidth=2)
    .encode(y=alt.Y("segmento_proveedor:N", sort=PERFILES, title=None),
            x=alt.X("n:Q", stack="normalize", title="Composición por tamaño de empresa",
                    axis=alt.Axis(format="%")),
            color=alt.Color("tamano_proveedor:N", title=None,
                            scale=alt.Scale(domain=["Microemprendedor", "Pequeña", "Mediana", "Grande"],
                                            range=d.SERIE),
                            legend=alt.Legend(orient="top")),
            order=alt.Order("orden:Q"),
            tooltip=[alt.Tooltip("segmento_proveedor:N", title="Perfil"),
                     alt.Tooltip("tamano_proveedor:N", title="Tamaño"),
                     alt.Tooltip("n:Q", title="Proveedores")])
    .transform_calculate(orden="indexof(['Microemprendedor','Pequeña','Mediana','Grande'], datum.tamano_proveedor)")
    .properties(height=200),
    width="stretch")
st.caption("Las MIPYMES están presentes en proporciones similares en los cuatro perfiles: "
           "el comportamiento distingue más que el tamaño (V de Cramér ≈ 0,05).")

st.divider()

# --- 2. Buscador de proveedor ---
st.subheader("Compara a un proveedor con su perfil")
texto = st.text_input("Nombre o cédula del proveedor", placeholder="Ej.: 3101…")
if texto:
    t = texto.strip().lower()
    hallados = seg[seg["nombre_proveedor"].str.lower().str.contains(t, na=False, regex=False)
                   | seg["cedula_proveedor"].str.contains(t, na=False, regex=False)]
    if hallados.empty:
        st.info("No se encontró el proveedor entre los segmentados. Solo se segmentan proveedores "
                "con al menos 5 líneas ofertadas ya resueltas (los demás son ocasionales).")
    else:
        opciones = hallados.sort_values("lineas_ofertadas", ascending=False).head(50)
        eleccion = st.selectbox("Proveedor", opciones.index,
                                format_func=lambda i: f"{opciones.at[i, 'nombre_proveedor']} "
                                                      f"({opciones.at[i, 'cedula_proveedor']})")
        p = opciones.loc[eleccion]
        ref = medianas.loc[p["segmento_proveedor"]]
        st.markdown(f"Perfil: **{p['segmento_proveedor']}** · tamaño: {p['tamano_proveedor']}")
        filas = [
            ("Líneas ofertadas", d.entero(p["lineas_ofertadas"]), d.entero(ref["lineas_ofertadas"])),
            ("Segmentos UNSPSC", d.entero(p["segmentos"]), d.entero(ref["segmentos"])),
            ("Instituciones", d.entero(p["instituciones"]), d.entero(ref["instituciones"])),
            ("Tasa de éxito (líneas resueltas)", d.porcentaje(p["tasa_exito"]), d.porcentaje(ref["tasa_exito"])),
            ("Competidores por línea", f"{p['competidores_promedio']:.1f}", f"{ref['competidores_promedio']:.1f}"),
            ("Monto por línea ganada", d.colones(p["ticket"]), d.colones(ref["ticket"])),
            ("Monto adjudicado total", d.colones(p["monto_adjudicado_crc"]), "—"),
        ]
        # Gráfico: posición (percentil) del proveedor y de la mediana de su perfil frente a
        # TODOS los proveedores segmentados. El percentil pone en una misma escala variables
        # con unidades distintas (líneas, %, colones).
        indicadores = {"lineas_ofertadas": "Líneas ofertadas", "segmentos": "Segmentos UNSPSC",
                       "instituciones": "Instituciones", "tasa_exito": "Tasa de éxito",
                       "competidores_promedio": "Competidores por línea",
                       "ticket": "Monto por línea ganada"}
        puntos = []
        for col, etiqueta in indicadores.items():
            puntos.append({"indicador": etiqueta, "quien": "Este proveedor",
                           "percentil": (seg[col] <= p[col]).mean()})
            puntos.append({"indicador": etiqueta, "quien": "Mediana del perfil",
                           "percentil": (seg[col] <= ref[col]).mean()})
        df_pct = pd.DataFrame(puntos)
        orden_ind = list(indicadores.values())
        lineas = alt.Chart(df_pct).mark_line(color="#c3c2b7", strokeWidth=2).encode(
            x="percentil:Q", y=alt.Y("indicador:N", sort=orden_ind), detail="indicador:N")
        marcas = alt.Chart(df_pct).mark_circle(size=140, opacity=1, stroke="#fcfcfb", strokeWidth=1.5).encode(
            x=alt.X("percentil:Q", title="Percentil entre los 1.990 proveedores segmentados",
                    axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("indicador:N", sort=orden_ind, title=None),
            color=alt.Color("quien:N", title=None,
                            scale=alt.Scale(domain=["Este proveedor", "Mediana del perfil"],
                                            range=d.SERIE[:2]),
                            legend=alt.Legend(orient="top")),
            tooltip=[alt.Tooltip("indicador:N", title="Indicador"), alt.Tooltip("quien:N", title=" "),
                     alt.Tooltip("percentil:Q", title="Percentil", format=".0%")])
        st.altair_chart((lineas + marcas).properties(height=280), width="stretch")
        st.caption("A la derecha = más que la mayoría de los proveedores. Ejemplo: percentil 80 % "
                   "en tasa de éxito significa que gana más que el 80 % de los proveedores.")
        st.dataframe(pd.DataFrame(filas, columns=["Indicador", "Este proveedor", "Mediana del perfil"]),
                     hide_index=True, width="stretch")

st.divider()

# --- 3. Mapa de oportunidades ---
st.subheader("Mapa de oportunidades por segmento de producto")
st.caption("Cada punto es un segmento UNSPSC. Abajo a la derecha: mucha demanda y poca "
           "competencia (hipótesis 3 del TFM). Calculado sobre procedimientos con ofertas registradas.")
if mapa is not None:
    mapa = mapa.assign(zona=mapa["oportunidad"].map({True: "Alta demanda, baja competencia",
                                                     False: "Resto"}),
                       sin_ofertas=mapa["pct_sin_ofertas"].apply(d.porcentaje))
    puntos = alt.Chart(mapa).mark_circle(size=90, stroke="#fcfcfb", strokeWidth=1, opacity=1).encode(
        x=alt.X("lineas_publicadas:Q", scale=alt.Scale(type="log"), title="Líneas publicadas (escala log)"),
        y=alt.Y("ofertas_por_linea:Q", title="Ofertas promedio por línea"),
        color=alt.Color("zona:N", title=None,
                        scale=alt.Scale(domain=["Alta demanda, baja competencia", "Resto"],
                                        range=[d.SERIE[0], d.GRIS]),
                        legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("nombre_segmento:N", title="Segmento"),
                 alt.Tooltip("lineas_publicadas:Q", title="Líneas publicadas", format=",.0f"),
                 alt.Tooltip("ofertas_por_linea:Q", title="Ofertas por línea", format=".2f"),
                 alt.Tooltip("sin_ofertas:N", title="Líneas sin ofertas")])
    reglas = alt.Chart(pd.DataFrame({"x": [mapa["lineas_publicadas"].median()]})) \
        .mark_rule(strokeDash=[4, 4], color="#898781").encode(x="x:Q")
    reglas_y = alt.Chart(pd.DataFrame({"y": [mapa["ofertas_por_linea"].median()]})) \
        .mark_rule(strokeDash=[4, 4], color="#898781").encode(y="y:Q")
    st.altair_chart((puntos + reglas + reglas_y).properties(height=440), width="stretch")
    with st.expander("Ver tabla"):
        st.dataframe(mapa.sort_values("lineas_publicadas", ascending=False)
                     [["nombre_segmento", "lineas_publicadas", "ofertas_por_linea", "sin_ofertas", "zona"]],
                     hide_index=True, width="stretch")
