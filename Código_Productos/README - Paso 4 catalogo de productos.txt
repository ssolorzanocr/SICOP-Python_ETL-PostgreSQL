=====================================================================
 PASO 4 — CARGA DEL CATÁLOGO DE PRODUCTOS (dim_catalogo_codigo_identificacion_producto)
 Proyecto SICOP — Grupo 2 — Aporte de André
 Archivo: "Paso 4 - script_carga_dim_catalogo_producto.sql"
=====================================================================

1. PROBLEMA QUE RESUELVE
---------------------------------------------------------------------
El pipeline original (Pasos 1 a 3) crea la dimensión de catálogo de
productos dim_catalogo_codigo_identificacion_producto (clave primaria
cod_producto, código de 16 dígitos) pero nunca la puebla:

  - El Observatorio de Compra Pública no publica un CSV de catálogo,
    por lo que el Paso 2 no tiene qué descargar.
  - El Paso 3 no contiene ningún INSERT hacia esa tabla.

Consecuencia: las tablas de líneas (lineas_carteles, lineas_ofertas,
lineas_adjudicadas) quedan con cod_producto sin dimensión contra la
cual hacer JOIN, y los análisis por segmento / familia / clase /
mercancía CABIS no son posibles. Por esa misma razón las claves
foráneas hacia el catálogo están comentadas en el DDL del Paso 1.

2. QUÉ HACE EL PASO 4
---------------------------------------------------------------------
Reconstruye el catálogo completo directamente desde el staging que el
Paso 2 ya cargó. No necesita archivos adicionales ni descargas extra:
funciona en la máquina de cualquier integrante que haya corrido los
Pasos 1 a 3.

  a) Une los códigos de producto de las cuatro fuentes del staging
     (codigo_identificacion de stg_lineas_carteles, codigo_producto_cl
     de stg_lineas_ofertadas, codigo_producto de stg_lineas_adjudicadas
     y prod_id de stg_procedimientos_adjudicacion), con el mismo
     tratamiento que usa el Paso 3: TRIM + SUBSTRING(...,1,16) +
     validación de 16 dígitos numéricos.

  b) Deriva la jerarquía CABIS del propio código. Estructura del
     código de producto de SICOP (basado en UNSPSC):
       Dígitos 1-2  -> Segmento
       Dígitos 1-4  -> Familia
       Dígitos 1-6  -> Clase
       Dígitos 1-8  -> Mercancía (artículo CABIS)
       Dígitos 9-16 -> Identificador interno del producto en SICOP

  c) Asigna nombre_segmento desde un lookup embebido en el propio
     script (57 segmentos CABIS/UNSPSC, catálogo maestro elaborado
     por André a partir de los datos históricos de adjudicaciones).

  d) Calcula descripcion_producto (por código de 16 dígitos) y
     nombre_mercancia (por artículo de 8 dígitos) como la descripción
     más frecuente observada en las líneas de cartel (moda
     determinística vía ROW_NUMBER; empates se resuelven por orden
     alfabético). nombre_familia y nombre_clase quedan NULL porque
     SICOP no publica esos nombres.

  e) Es idempotente: TRUNCATE + INSERT. Puede re-ejecutarse cuantas
     veces se quiera, por ejemplo tras ampliar MESES_A_DESCARGAR en
     el Paso 2 y recargar el staging.

3. CÓMO EJECUTARLO
---------------------------------------------------------------------
Después del Paso 3, en la misma base proyecto_sicop_v1 (pgAdmin 4 o
psql):

    psql -d proyecto_sicop_v1 -f "Paso 4 - script_carga_dim_catalogo_producto.sql"

Al final del script hay consultas de verificación comentadas:
totales, % con descripción/segmento y cobertura de cod_producto en
las tres tablas de líneas.

4. VALIDACIÓN REALIZADA
---------------------------------------------------------------------
Probado de punta a punta en PostgreSQL 18 con datos reales de 17
periodos mensuales (2025-2026), ejecutando el pipeline completo
(Paso 1 -> carga de staging con la lógica del Paso 2, 1,79 millones
de filas -> Paso 3 -> Paso 4):

  - 83.354 productos distintos de 16 dígitos en el catálogo
    (tiempo de carga: ~2 min 15 s).
  - 100% de los productos con segmento y nombre de segmento
    (el lookup de 57 segmentos cubre todos los códigos observados).
  - 95,8% con descripción de producto (el resto son códigos que solo
    aparecen en ofertas/adjudicaciones, sin línea de cartel asociada).
  - Cobertura 100%: todo cod_producto de lineas_carteles (250.727),
    lineas_ofertas (143.855) y lineas_adjudicadas (49.854) tiene su
    fila en la dimensión — cero registros huérfanos. Las FK comentadas
    del Paso 1 quedan listas para activarse si el grupo lo decide.
  - Idempotencia verificada: segunda ejecución completa sin errores,
    mismo resultado.
  - Consistencia verificada contra el catálogo CABIS de André
    (clasificacion_cabis_16digitos.xlsx, 22.728 códigos adjudicados):
    jerarquía y nombres de segmento coinciden en el 100% de los
    códigos en común.

5. RELACIÓN CON EL TRABAJO PREVIO DEL GRUPO
---------------------------------------------------------------------
Este paso integra al pipeline común el trabajo de clasificación CABIS
documentado en la sección "Enfoque de modelado de datos (André)" del
documento del grupo:

  - Catálogo maestro de artículos de 8 dígitos (dim_cabis.sql /
    clasificacion_cabis.xlsx, 5.699 artículos).
  - Catálogo a nivel de producto de 16 dígitos (dim_producto.sql /
    clasificacion_cabis_16digitos.xlsx).
  - Consultas de los casos de uso UC1/UC2/UC3 (queries_cabis.sql).

La tabla poblada corresponde a la entidad
DIM_Catalogo_CodigoIdentificacion_Producto del diagrama
entidad-relación del grupo. Con la dimensión cargada, las consultas
de los casos de uso y el modelo predictivo del TFM pueden ejecutarse
sobre la base que cualquier integrante construye con los Pasos 1 a 4.
