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
-- Consultas del prototipo Streamlit por segmento CABIS (André)
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