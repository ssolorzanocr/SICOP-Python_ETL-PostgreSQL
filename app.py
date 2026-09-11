import streamlit as st
import psycopg2
import pandas as pd
import altair as alt

st.title("SICOP - Compras Públicas de Costa Rica")

db = st.secrets["postgres"]

conexion = psycopg2.connect(
    host=db["host"],
    port=db["port"],
    database=db["database"],
    user=db["user"],
    password=db["password"]
)

st.success("Conectado a PostgreSQL")

consulta_instituciones = """
SELECT
    i.nombre_institucion,
    COUNT(DISTINCT lc.nro_sicop) AS carteles_publicados
FROM lineas_carteles lc
JOIN dim_instituciones i
    ON lc.cedula_institucion = i.cedula_institucion
WHERE lc.fecha_publicacion >= (
    SELECT MAX(fecha_publicacion) - INTERVAL '7 months'
    FROM lineas_carteles
)
GROUP BY i.nombre_institucion
ORDER BY carteles_publicados DESC
LIMIT 20;
"""

df_instituciones = pd.read_sql_query(
    consulta_instituciones,
    conexion
)

st.subheader("Top 20 instituciones con más carteles publicados")

grafico = (
    alt.Chart(df_instituciones)
    .mark_bar()
    .encode(
        x=alt.X(
            "carteles_publicados:Q",
            title="Cantidad de carteles"
        ),
        y=alt.Y(
            "nombre_institucion:N",
            sort="-x",
            title=None
        ),
        tooltip=[
            alt.Tooltip(
                "nombre_institucion:N",
                title="Institución"
            ),
            alt.Tooltip(
                "carteles_publicados:Q",
                title="Carteles"
            )
        ]
    )
    .properties(
        height=600
    )
)

st.altair_chart(
    grafico,
    use_container_width=True
)

conexion.close()