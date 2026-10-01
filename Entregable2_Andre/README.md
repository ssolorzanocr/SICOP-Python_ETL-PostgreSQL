# Entregable 2 · Componente de André Plannerer

TFM Grupo 2 — Máster en Big Data & Business Intelligence (Next Educación).
Segundo entregable (18/10/2026): Asignatura 7 (análisis no supervisado) y aplicación
Streamlit con los tres casos de uso del primer avance.

La explicación completa, con el porqué de cada decisión y el registro de cambios de
código, está en [`LEEME_por_que_de_cada_cosa.txt`](LEEME_por_que_de_cada_cosa.txt).

## Contenido

| Carpeta | Qué hay |
|---|---|
| `notebooks/` | `clustering_proveedores.ipynb` (+ `.html`): segmentación de proveedores con KMeans, mapa de oportunidades y análisis complementarios. `features.sql`: tabla por proveedor. |
| `app/` | Aplicación Streamlit sobre DuckDB: UC1 demanda institucional, UC2 caracterización de proveedores, UC3 probabilidad de adjudicación. |
| `figuras/` | Figuras 1–9 del análisis y capturas de la aplicación. |
| `textos/` | Secciones en Word para la memoria de la Asig. 7 y para el TFM, y mensaje para el grupo. |

## Cómo ejecutar

Requisitos: Python 3.11+ y el archivo `sicop.duckdb` del release
[`datos_actuales_sicop`](https://github.com/ssolorzanocr/Modelo_predictivo_SICOP/releases/tag/datos_actuales_sicop)
del repositorio `Modelo_predictivo_SICOP`.

```bash
# 1. Entorno
python -m venv .venv
.venv/Scripts/python -m pip install -r Entregable2_Andre/app/requirements.txt
.venv/Scripts/python -m pip install scikit-learn scipy matplotlib jupyter nbconvert python-docx

# 2. Base de datos: dejar sicop.duckdb en Modelo_predictivo_SICOP/data/ en alguna carpeta
#    superior, o indicar la ruta con la variable de entorno SICOP_DUCKDB.

# 3. Aplicación
cd Entregable2_Andre/app
python -m streamlit run app.py

# 4. Prueba de las 3 páginas sin navegador
python tests/prueba_paginas.py

# 5. Rehacer el cuaderno con datos nuevos
cd ../notebooks
python _genera_notebook.py
python -m jupyter nbconvert --to notebook --execute --inplace clustering_proveedores.ipynb
python -m jupyter nbconvert --to html clustering_proveedores.ipynb
```

## Resultados principales

- Cuatro perfiles de proveedor: Generalistas de alto volumen (450), Competidores
  focalizados (653), Nicho con poca competencia (502) y Sin adjudicaciones (385).
- El tamaño de empresa casi no explica el perfil (V de Cramér = 0,05): las MIPYMES
  están en todos los grupos.
- 11 segmentos UNSPSC combinan alta demanda y baja competencia (hipótesis 3).
- La oferta más barata gana solo en el 56 % de las líneas con competencia.

## Limitaciones conocidas de los datos (release del 24/09/2026)

- Solo ~12 % de los procedimientos tiene ofertas registradas.
- `tipo_cambio_crc` es siempre el tipo de cambio del dólar: solo se convierten CRC y USD.
- Las probabilidades del modelo supervisado parecen no estar calibradas; la app las
  muestra como orden relativo.
