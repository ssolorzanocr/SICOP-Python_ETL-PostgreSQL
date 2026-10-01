-- Una fila por proveedor que ofertó al menos una vez (ene/2025 - set/2026).
WITH ofertas AS (
    SELECT o.nro_sicop, o.nro_linea, o.nro_oferta, o.cedula_proveedor, o.cod_producto,
           CASE WHEN o.tipo_moneda = 'CRC' THEN o.precio_unitario_ofertado
                WHEN o.tipo_moneda = 'USD' AND o.tipo_cambio_crc > 0
                     THEN o.precio_unitario_ofertado * o.tipo_cambio_crc
           END AS precio_crc
    FROM final.fact_lineas_ofertas o
),
-- líneas ya resueltas: alguien fue adjudicado (evita contar como "perdidas"
-- las ofertas en líneas que siguen en evaluación)
resueltas AS (
    SELECT DISTINCT nro_sicop, nro_linea FROM final.fact_lineas_adjudicadas
),
ganadas AS (
    SELECT DISTINCT nro_sicop, nro_linea, cedula_proveedor FROM final.fact_lineas_adjudicadas
),
linea_stats AS (
    SELECT nro_sicop, nro_linea,
           COUNT(*)            AS ofertas_en_linea,
           MEDIAN(precio_crc)  AS precio_mediana_linea
    FROM ofertas GROUP BY ALL
),
det AS (
    SELECT o.*, ls.ofertas_en_linea,
           CASE WHEN ls.ofertas_en_linea >= 2 AND ls.precio_mediana_linea > 0
                THEN o.precio_crc / ls.precio_mediana_linea END AS precio_relativo,
           r.nro_sicop IS NOT NULL AS resuelta,
           g.nro_sicop IS NOT NULL AS ganada,
           p.segmento
    FROM ofertas o
    JOIN linea_stats ls USING (nro_sicop, nro_linea)
    LEFT JOIN resueltas r USING (nro_sicop, nro_linea)
    LEFT JOIN ganadas g ON g.nro_sicop = o.nro_sicop AND g.nro_linea = o.nro_linea
                       AND g.cedula_proveedor = o.cedula_proveedor
    LEFT JOIN final.dim_productos p ON p.cod_producto = TRY_CAST(o.cod_producto AS BIGINT)
),
inst AS (
    SELECT o.cedula_proveedor, COUNT(DISTINCT c.cedula_institucion) AS instituciones
    FROM ofertas o
    JOIN (SELECT DISTINCT nro_sicop, cedula_institucion FROM final.fact_lineas_carteles) c USING (nro_sicop)
    GROUP BY 1
),
adj AS (
    SELECT cedula_proveedor,
           SUM(CASE WHEN tipo_moneda = 'CRC' THEN monto_adjudicado_linea
                    WHEN tipo_moneda = 'USD' AND tipo_cambio_crc > 0
                         THEN monto_adjudicado_linea * tipo_cambio_crc END) AS monto_adjudicado_crc
    FROM final.fact_lineas_adjudicadas GROUP BY 1
)
SELECT d.cedula_proveedor,
       pr.tamano_proveedor, pr.tipo_proveedor, pr.zona_geo_prov,
       COUNT(*)                                        AS lineas_ofertadas,
       COUNT(DISTINCT d.nro_sicop)                     AS procedimientos,
       COUNT(DISTINCT d.segmento)                      AS segmentos,
       ANY_VALUE(i.instituciones)                      AS instituciones,
       COUNT(*) FILTER (WHERE d.resuelta)              AS lineas_resueltas,
       COUNT(*) FILTER (WHERE d.resuelta AND d.ganada) AS lineas_ganadas,
       AVG(d.ofertas_en_linea - 1)                     AS competidores_promedio,
       MEDIAN(d.precio_relativo)                       AS precio_relativo_mediana,
       COALESCE(ANY_VALUE(a.monto_adjudicado_crc), 0)  AS monto_adjudicado_crc
FROM det d
LEFT JOIN inst i USING (cedula_proveedor)
LEFT JOIN adj a USING (cedula_proveedor)
LEFT JOIN final.dim_proveedores pr USING (cedula_proveedor)
GROUP BY d.cedula_proveedor, pr.tamano_proveedor, pr.tipo_proveedor, pr.zona_geo_prov
