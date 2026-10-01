"""
UC3 — Predicción de adjudicación.

Muestra las probabilidades que el modelo supervisado del grupo (Random Forest,
Asignatura 7, responsable: Sergio Solórzano) calcula cada día para las ofertas
todavía no resueltas. La aplicación NO carga el modelo (.joblib de ~770 MB): lee
la tabla `final.predicciones_adjudicacion` que el pipeline escribe tras entrenar.
Así la app sigue siendo ligera y el modelo se actualiza sin tocar la app.
"""

import altair as alt
import streamlit as st

import datos as d

d.verificar_conexion()


@st.cache_data(ttl=3600)
def predicciones():
    return d.consultar(f"""
        SELECT pr.cedula_proveedor, pv.nombre_proveedor, pv.tamano_proveedor,
               pr.nro_sicop, pr.nro_linea, c.cartel_nm AS cartel, c.desc_linea,
               i.nombre_institucion, c.cartel_stat AS estado, c.fecha_publicacion,
               {d.a_crc('o.precio_unitario_ofertado', 'o.tipo_moneda', 'o.tipo_cambio_crc')} AS precio_ofertado_crc,
               pr.probabilidad_adjudicacion AS probabilidad,
               PERCENT_RANK() OVER (ORDER BY pr.probabilidad_adjudicacion) AS percentil
        FROM final.predicciones_adjudicacion pr
        LEFT JOIN final.fact_lineas_carteles c
               ON c.nro_sicop = pr.nro_sicop AND c.numero_linea = pr.nro_linea
        LEFT JOIN final.fact_lineas_ofertas o
               ON o.nro_sicop = pr.nro_sicop AND o.nro_linea = pr.nro_linea AND o.nro_oferta = pr.nro_oferta
        LEFT JOIN final.dim_proveedores pv ON pv.cedula_proveedor = pr.cedula_proveedor
        LEFT JOIN final.dim_instituciones i ON i.cedula = c.cedula_institucion
    """)


st.title("Probabilidad de adjudicación")
st.caption("**Caso de uso 3.** De mis ofertas en curso, ¿cuáles tienen más posibilidades? "
           "¿Dónde conviene concentrar el esfuerzo?")

st.warning("**Prototipo.** Las probabilidades provienen del modelo del grupo en su versión "
           "actual, todavía en validación (Asignatura 7). Úsalas para **ordenar** las ofertas "
           "entre sí, no como probabilidad exacta.", icon="⚠️")

df = predicciones()
st.caption(f"{d.entero(len(df))} ofertas pendientes de {d.entero(df['cedula_proveedor'].nunique())} "
           f"proveedores con predicción.")

texto = st.text_input("Nombre o cédula del proveedor", placeholder="Ej.: 3101…")
if not texto:
    st.info("Escribe el nombre o la cédula de un proveedor para ver sus ofertas en curso.")
    st.subheader("Distribución de las probabilidades estimadas")
    st.altair_chart(
        alt.Chart(df).mark_bar(color=d.SERIE[0], cornerRadiusEnd=4)
        .encode(x=alt.X("probabilidad:Q", bin=alt.Bin(step=0.05), title="Probabilidad estimada",
                        axis=alt.Axis(format="%")),
                y=alt.Y("count():Q", title="Ofertas"),
                tooltip=[alt.Tooltip("probabilidad:Q", bin=alt.Bin(step=0.05), title="Rango", format=".0%"),
                         alt.Tooltip("count():Q", title="Ofertas")])
        .properties(height=280),
        width="stretch")
    st.stop()

t = texto.strip().lower()
prov = df[df["nombre_proveedor"].str.lower().str.contains(t, na=False, regex=False)
          | df["cedula_proveedor"].str.contains(t, na=False, regex=False)]
if prov.empty:
    st.info("Ese proveedor no tiene ofertas pendientes con predicción.")
    st.stop()

nombres = (prov.drop_duplicates("cedula_proveedor").sort_values("nombre_proveedor")
           .set_index("cedula_proveedor")["nombre_proveedor"])
ced = st.selectbox("Proveedor", nombres.index, format_func=lambda c: f"{nombres[c]} ({c})")
mias = prov[prov["cedula_proveedor"] == ced].sort_values("probabilidad", ascending=False)

m = st.columns(3)
m[0].metric("Ofertas en curso", d.entero(len(mias)))
m[1].metric("En el tercio superior", d.entero((mias["percentil"] >= 2 / 3).sum()),
            help="Ofertas cuya probabilidad está entre el 33 % más alto de todas las predicciones.")
m[2].metric("Probabilidad mediana", d.porcentaje(mias["probabilidad"].median(), 1))

mias = mias.assign(
    prioridad=mias["percentil"].map(lambda p: "Alta" if p >= 2 / 3 else ("Media" if p >= 1 / 3 else "Baja")),
    probabilidad_fmt=mias["probabilidad"].apply(lambda v: d.porcentaje(v, 1)),
    precio=mias["precio_ofertado_crc"].apply(d.colones),
)
st.dataframe(
    mias[["prioridad", "probabilidad_fmt", "cartel", "desc_linea", "nombre_institucion",
          "estado", "precio", "fecha_publicacion"]]
    .rename(columns={"prioridad": "Prioridad relativa", "probabilidad_fmt": "Probabilidad",
                     "cartel": "Cartel", "desc_linea": "Línea", "nombre_institucion": "Institución",
                     "estado": "Estado", "precio": "Precio ofertado", "fecha_publicacion": "Publicación"}),
    hide_index=True, width="stretch")
st.caption("Prioridad relativa: posición de cada oferta dentro de todas las predicciones "
           "(tercio superior = Alta). Se muestra junto a la probabilidad porque el modelo aún no "
           "está calibrado.")
