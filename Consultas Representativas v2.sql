-- Agrupacion de carteles ganados por Proveedor
/*
SELECT i.nombre_institucion,
       COUNT(DISTINCT la.nro_sicop)   AS carteles_ganados,
       SUM(la.monto_adjudicado_linea) AS monto_total_adjudicado
FROM lineas_adjudicadas la
JOIN dim_instituciones i
  ON la.cedula_institucion = i.cedula_institucion
WHERE la.cedula_proveedor = '3101005744' --Proveedor de Prueba:Purdy Motors
GROUP BY i.nombre_institucion
ORDER BY monto_total_adjudicado DESC;
*/

-- Adjudicacion de montos mas altos por proveedor
/*
SELECT p.cedula_proveedor,
       p.nombre_proveedor,
       i.nombre_institucion,
       COUNT(DISTINCT la.nro_sicop)   AS carteles_ganados,
       SUM(la.monto_adjudicado_linea) AS monto_total_adjudicado
FROM lineas_adjudicadas la
JOIN dim_instituciones i
  ON la.cedula_institucion = i.cedula_institucion
JOIN dim_proveedores p
  ON la.cedula_proveedor = p.cedula_proveedor
GROUP BY p.cedula_proveedor, p.nombre_proveedor, i.nombre_institucion
ORDER BY monto_total_adjudicado DESC;
*/

--Top 20 de instituciones con mas carteles publicados por mes
/*
SELECT i.nombre_institucion,
       COUNT(DISTINCT lc.nro_sicop) AS carteles_publicados
FROM lineas_carteles lc
JOIN dim_instituciones i
  ON lc.cedula_institucion = i.cedula_institucion
WHERE EXTRACT(MONTH FROM lc.fecha_publicacion) = 1
  AND EXTRACT(YEAR  FROM lc.fecha_publicacion) = 2026   -- ajusta el año
GROUP BY i.nombre_institucion
ORDER BY carteles_publicados DESC
LIMIT 20;
*/

-- ============================================================
-- Consultas del prototipo Streamlit por segmento de producto UNSPSC (André)
-- Caso de uso: "un proveedor MIPYME quiere descubrir y evaluar
-- los carteles de su segmento de producto".
-- Ejemplo de valores: segmento = 'Equipos y suministros médicos',
-- meses = 12. En app.py estos valores se pasan como parámetros
-- (:segmento, :meses) en vez de literales.
-- ============================================================

-- Segmentos disponibles, ordenados por volumen (para el selectbox)
/*
SELECT c.nombre_segmento,
       COUNT(*) AS lineas_publicadas
FROM lineas_carteles lc
JOIN dim_catalogo_codigo_identificacion_producto c
    ON lc.cod_producto = c.cod_producto
WHERE c.nombre_segmento IS NOT NULL
GROUP BY c.nombre_segmento
ORDER BY lineas_publicadas DESC;
*/

-- KPIs del segmento: carteles publicados, monto adjudicado,
-- proveedores distintos que ofertaron y promedio de ofertas por
-- línea (indicador de competencia)
/*
WITH periodo AS (
    SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
),
carteles_seg AS (
    SELECT lc.nro_sicop, lc.nro_linea, lc.nro_sicop_nro_linea
    FROM lineas_carteles lc
    JOIN dim_catalogo_codigo_identificacion_producto c
        ON lc.cod_producto = c.cod_producto
    CROSS JOIN periodo p
    WHERE c.nombre_segmento = 'Equipos y suministros médicos'
      AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
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
*/

-- Instituciones mas activas dentro de un segmento
/*
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
WHERE c.nombre_segmento = 'Equipos y suministros médicos'
  AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
GROUP BY i.nombre_institucion
ORDER BY carteles_publicados DESC
LIMIT 20;
*/

-- Ranking de proveedores por monto adjudicado dentro de un segmento
/*
WITH periodo AS (
    SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
),
carteles_seg AS (
    SELECT lc.nro_sicop, lc.nro_linea
    FROM lineas_carteles lc
    JOIN dim_catalogo_codigo_identificacion_producto c
        ON lc.cod_producto = c.cod_producto
    CROSS JOIN periodo p
    WHERE c.nombre_segmento = 'Equipos y suministros médicos'
      AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
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
*/

-- Evolucion mensual: carteles publicados vs. adjudicados, por segmento
/*
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
WHERE c.nombre_segmento = 'Equipos y suministros médicos'
  AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
GROUP BY 1

UNION ALL

SELECT DATE_TRUNC('month', la.fecha_adjud_firme) AS mes,
       COUNT(DISTINCT la.nro_sicop) AS cantidad,
       'Adjudicados' AS tipo
FROM lineas_adjudicadas la
JOIN dim_catalogo_codigo_identificacion_producto c
    ON la.cod_producto = c.cod_producto
CROSS JOIN periodo p
WHERE c.nombre_segmento = 'Equipos y suministros médicos'
  AND la.fecha_adjud_firme >= (p.max_fecha - make_interval(months => 12))::date
GROUP BY 1

ORDER BY mes;
*/

-- Detalle de los ultimos carteles publicados en un segmento
/*
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
    WHERE c.nombre_segmento = 'Equipos y suministros médicos'
      AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
    ORDER BY lc.nro_sicop, lc.fecha_publicacion DESC
) sub
ORDER BY fecha_publicacion DESC
LIMIT 30;
*/
-- ============================================================
-- UC1 completo: precios y tiempos de adjudicación (André, 13/09)
-- Conversión de moneda usada en todas las consultas de precio:
--   tipo_moneda = 'CRC'  -> precio tal cual
--   tipo_cambio_crc > 0  -> precio * tipo_cambio_crc
--   en otro caso         -> NULL (la línea se excluye)
-- PENDIENTE: confirmar contra la base el literal de tipo_moneda
-- para colones y la semántica de tipo_cambio_crc.
-- ============================================================

-- Razón precio adjudicado / estimado (y ofertado / estimado), mediana
-- línea a línea dentro del segmento. 0,88 = las adjudicaciones cierran
-- un 12 % por debajo del estimado.
/*
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
    WHERE c.nombre_segmento = 'Equipos y suministros médicos'
      AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
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
    WHERE la.precio_unitario_adjudicado > 0 AND cs.precio_est_crc > 0
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
    WHERE lo.precio_unitario_ofertado > 0 AND cs.precio_est_crc > 0
)
SELECT
    (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY razon)
     FROM razon_adj WHERE razon IS NOT NULL) AS razon_adj_est_mediana,
    (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY razon)
     FROM razon_of WHERE razon IS NOT NULL)  AS razon_of_est_mediana,
    (SELECT COUNT(*) FROM razon_adj WHERE razon IS NOT NULL) AS lineas_adjudicadas_con_precio,
    (SELECT COUNT(*) FROM razon_of  WHERE razon IS NOT NULL) AS lineas_ofertadas_con_precio;
*/

-- Precios por producto: mediana del precio unitario estimado, ofertado y
-- adjudicado (en colones) para los productos más demandados del segmento.
-- Cada mediana se calcula por separado para que la cantidad de ofertas de
-- una línea no pese sobre el estimado ni sobre el adjudicado.
/*
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
    WHERE c.nombre_segmento = 'Equipos y suministros médicos'
      AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
),
est AS (
    SELECT cod_producto, COUNT(DISTINCT nro_sicop) AS carteles,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio_est_crc) AS precio_estimado_mediana
    FROM lineas_seg WHERE precio_est_crc > 0 GROUP BY cod_producto
),
ofe AS (
    SELECT ls.cod_producto,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
               CASE WHEN lo.tipo_moneda = 'CRC' THEN lo.precio_unitario_ofertado
                    WHEN lo.tipo_cambio_crc > 0 THEN lo.precio_unitario_ofertado * lo.tipo_cambio_crc
               END) AS precio_ofertado_mediana
    FROM lineas_ofertas lo
    JOIN lineas_seg ls ON lo.nro_sicop = ls.nro_sicop AND lo.nro_linea = ls.nro_linea
    WHERE lo.precio_unitario_ofertado > 0 GROUP BY ls.cod_producto
),
adj AS (
    SELECT ls.cod_producto,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
               CASE WHEN la.moneda_adjudicada = 'CRC' THEN la.precio_unitario_adjudicado
                    WHEN la.tipo_cambio_crc > 0 THEN la.precio_unitario_adjudicado * la.tipo_cambio_crc
               END) AS precio_adjudicado_mediana
    FROM lineas_adjudicadas la
    JOIN lineas_seg ls ON la.nro_sicop = ls.nro_sicop AND la.nro_linea = ls.nro_linea
    WHERE la.precio_unitario_adjudicado > 0 GROUP BY ls.cod_producto
)
SELECT c.cod_producto,
       COALESCE(c.descripcion_producto, c.nombre_mercancia, c.cod_producto::text) AS producto,
       est.carteles, est.precio_estimado_mediana,
       ofe.precio_ofertado_mediana, adj.precio_adjudicado_mediana
FROM est
JOIN dim_catalogo_codigo_identificacion_producto c ON est.cod_producto = c.cod_producto
LEFT JOIN ofe ON ofe.cod_producto = est.cod_producto
LEFT JOIN adj ON adj.cod_producto = est.cod_producto
ORDER BY est.carteles DESC, c.cod_producto
LIMIT 15;
*/

-- Días entre publicación del cartel y adjudicación firme: mediana, P25, P75.
-- (La Asignatura 5 midió desde FECHA_SOL_CONTRA; aquí desde fecha_publicacion.)
/*
WITH periodo AS (
    SELECT MAX(fecha_publicacion) AS max_fecha FROM lineas_carteles
),
tiempos AS (
    SELECT (la.fecha_adjud_firme - lc.fecha_publicacion::date) AS dias
    FROM lineas_adjudicadas la
    JOIN lineas_carteles lc ON la.nro_sicop = lc.nro_sicop AND la.nro_linea = lc.nro_linea
    JOIN dim_catalogo_codigo_identificacion_producto c ON lc.cod_producto = c.cod_producto
    CROSS JOIN periodo p
    WHERE c.nombre_segmento = 'Equipos y suministros médicos'
      AND lc.fecha_publicacion >= p.max_fecha - make_interval(months => 12)
      AND la.fecha_adjud_firme IS NOT NULL
      AND la.fecha_adjud_firme >= lc.fecha_publicacion::date
)
SELECT PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY dias) AS dias_mediana,
       PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY dias) AS dias_p25,
       PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY dias) AS dias_p75,
       COUNT(*) AS lineas_adjudicadas
FROM tiempos;
*/
