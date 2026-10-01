"""
SICOP — Herramienta de inteligencia de negocio para proveedores MIPYME.
TFM Grupo 2 · Máster en Big Data & Business Intelligence (Next Educación).

Punto de entrada. Una página por caso de uso del primer avance (Tabla 1):
    UC1 Comportamiento de la demanda institucional
    UC2 Caracterización de proveedores
    UC3 Predicción de adjudicación

Ejecutar desde esta carpeta:  streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="SICOP · Inteligencia para proveedores", layout="wide")

paginas = st.navigation([
    st.Page("paginas/uc1_demanda.py", title="Demanda institucional", icon="🏛️", default=True),
    st.Page("paginas/uc2_proveedores.py", title="Caracterización de proveedores", icon="🏷️"),
    st.Page("paginas/uc3_prediccion.py", title="Probabilidad de adjudicación", icon="🎯"),
])

with st.sidebar:
    st.caption("Prototipo del TFM · datos públicos del Observatorio de Compra Pública "
               "(SICOP), actualizados por el pipeline diario del grupo.")

paginas.run()
