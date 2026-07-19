-- ============================================================
--  PASO 4 — Carga de dim_catalogo_codigo_identificacion_producto
--  Proyecto SICOP — Grupo 2 — André
--
--  PROBLEMA QUE RESUELVE:
--    El Paso 1 crea la dimensión de catálogo de productos
--    (dim_catalogo_codigo_identificacion_producto, PK cod_producto)
--    pero ni el Paso 2 ni el Paso 3 la pueblan: las tablas de líneas
--    (lineas_carteles, lineas_ofertas, lineas_adjudicadas) quedan con
--    cod_producto sin dimensión contra la cual hacer JOIN, y los
--    análisis por segmento/familia/clase CABIS no son posibles.
--
--  QUÉ HACE ESTE SCRIPT:
--    Reconstruye el catálogo completo directamente desde el staging
--    ya cargado por el Paso 2 — no requiere archivos adicionales,
--    funciona en la máquina de cualquier integrante del grupo.
--
--  ESTRUCTURA DEL CÓDIGO DE PRODUCTO (16 dígitos, basado en UNSPSC):
--    Dígitos 1-2  → Segmento
--    Dígitos 1-4  → Familia
--    Dígitos 1-6  → Clase
--    Dígitos 1-8  → Mercancía (artículo CABIS)
--    Dígitos 9-16 → ID interno SICOP del producto
--
--  FUENTES (staging):
--    stg_lineas_carteles.codigo_identificacion  + desc_linea
--    stg_lineas_ofertadas.codigo_producto_cl
--    stg_lineas_adjudicadas.codigo_producto
--    stg_procedimientos_adjudicacion.prod_id
--    La unión de las cuatro garantiza que todo cod_producto presente
--    en las tablas de líneas exista en la dimensión (cero huérfanos).
--
--  NOTAS:
--    - nombre_segmento proviene de un lookup embebido (57 segmentos
--      CABIS/UNSPSC, catálogo maestro elaborado por André).
--    - nombre_familia y nombre_clase quedan NULL: SICOP no publica
--      esos nombres en los CSV del observatorio.
--    - nombre_mercancia = descripción más frecuente entre los
--      productos que comparten el mismo artículo de 8 dígitos.
--    - Idempotente: TRUNCATE + INSERT (la dimensión es 100%
--      derivable del staging; las FK del Paso 1 están comentadas).
--
--  EJECUTAR DESPUÉS DEL PASO 3, en la misma base proyecto_sicop_v1.
-- ============================================================

TRUNCATE TABLE dim_catalogo_codigo_identificacion_producto;

INSERT INTO dim_catalogo_codigo_identificacion_producto (
    cod_producto,
    descripcion_producto,
    segmento,
    nombre_segmento,
    familia,
    nombre_familia,
    clases,
    nombre_clase,
    mercancias,
    nombre_mercancia
)
WITH codigos_crudos AS (
    -- Unión de todas las fuentes de código de producto en staging.
    -- Mismo tratamiento que el Paso 3: TRIM + SUBSTRING(...,1,16).
    SELECT SUBSTRING(TRIM(codigo_identificacion), 1, 16) AS cod_producto,
           TRIM(desc_linea)                              AS descr
    FROM   staging.stg_lineas_carteles

    UNION ALL

    SELECT SUBSTRING(TRIM(codigo_producto_cl), 1, 16), NULL
    FROM   staging.stg_lineas_ofertadas

    UNION ALL

    SELECT SUBSTRING(TRIM(codigo_producto), 1, 16), NULL
    FROM   staging.stg_lineas_adjudicadas

    UNION ALL

    SELECT SUBSTRING(TRIM(prod_id), 1, 16), NULL
    FROM   staging.stg_procedimientos_adjudicacion
),
limpio AS (
    -- Solo códigos válidos de exactamente 16 dígitos
    SELECT cod_producto, NULLIF(descr, '') AS descr
    FROM   codigos_crudos
    WHERE  cod_producto ~ '^[0-9]{16}$'
),
codigos AS (
    SELECT DISTINCT cod_producto
    FROM   limpio
),
conteo AS (
    -- Frecuencia de cada descripción por código
    SELECT cod_producto, descr, COUNT(*) AS n
    FROM   limpio
    WHERE  descr IS NOT NULL
    GROUP  BY cod_producto, descr
),
moda_producto AS (
    -- Descripción más frecuente por código de 16 dígitos
    -- (empate → orden alfabético, resultado determinístico)
    SELECT cod_producto,
           descr AS descripcion_producto,
           ROW_NUMBER() OVER (PARTITION BY cod_producto
                              ORDER BY n DESC, descr) AS rk
    FROM   conteo
),
moda_mercancia AS (
    -- Descripción más frecuente por mercancía (prefijo de 8 dígitos)
    SELECT SUBSTRING(cod_producto, 1, 8) AS cod_mercancia,
           descr AS nombre_mercancia,
           ROW_NUMBER() OVER (PARTITION BY SUBSTRING(cod_producto, 1, 8)
                              ORDER BY SUM(n) DESC, descr) AS rk
    FROM   conteo
    GROUP  BY SUBSTRING(cod_producto, 1, 8), descr
),
segmentos (segmento, nombre_segmento) AS (
    -- Lookup embebido: 57 segmentos CABIS/UNSPSC
    -- (catálogo maestro CABIS — André, Grupo 2)
    VALUES
    (10, 'Animales vivos, accesorios y suministros'),
    (11, 'Material mineral, textil y vegetal'),
    (12, 'Productos químicos incluyendo bioquímicos'),
    (13, 'Resinas, caucho y espuma'),
    (14, 'Papel, materiales de oficina y artículos de arte'),
    (15, 'Combustibles, lubricantes y aceites'),
    (20, 'Equipos de minería y cantería'),
    (21, 'Equipos de granja y jardín y silvicultura'),
    (22, 'Equipos de construcción y mantenimiento'),
    (23, 'Maquinaria industrial y equipos de manufactura'),
    (24, 'Materiales y accesorios de manejo de materiales'),
    (25, 'Vehículos comerciales, militares y de uso personal'),
    (26, 'Componentes y suministros de potencia generación y transmisión'),
    (27, 'Herramientas y maquinaria general'),
    (30, 'Estructuras, edificaciones, fabricaciones y acondicionamiento de espacios'),
    (31, 'Materiales de manufactura y procesamiento'),
    (32, 'Componentes electrónicos'),
    (39, 'Iluminación, distribución eléctrica y accesorios'),
    (40, 'Equipos de distribución y condicionamiento de fluidos'),
    (41, 'Instrumentos de laboratorio, medición y observación'),
    (42, 'Equipo médico, accesorios e insumos'),
    (43, 'Tecnología de información, telecomunicaciones y radiodifusión'),
    (44, 'Suministros de oficina, accesorios y consumibles'),
    (45, 'Imprenta, equipos fotográficos y audiovisuales'),
    (46, 'Seguridad, protección y defensa'),
    (47, 'Limpieza y mantenimiento de instalaciones y productos'),
    (48, 'Equipos y suministros industriales'),
    (49, 'Deportes, recreación, entretenimiento y educación'),
    (50, 'Productos alimenticios, bebidas y tabaco'),
    (51, 'Medicamentos y productos farmacéuticos'),
    (52, 'Ropa, calzado y accesorios de uso personal'),
    (53, 'Artículos domésticos, personales y de consumo'),
    (54, 'Artículos de uso público y eventos'),
    (55, 'Publicaciones, grabaciones y medios de información'),
    (56, 'Mobiliario y decoración'),
    (60, 'Instrumentos musicales, artes y manualidades'),
    (64, 'Artículos de colección y bellas artes'),
    (70, 'Servicios de agricultura, pesca, silvicultura y caza'),
    (71, 'Servicios de minería y petróleo y gas'),
    (72, 'Servicios de construcción y mantenimiento de edificios'),
    (73, 'Servicios de manufactura industrial'),
    (76, 'Servicios de limpieza industrial'),
    (77, 'Servicios medioambientales'),
    (78, 'Servicios de transporte, almacenamiento y correo'),
    (80, 'Servicios profesionales de gestión y administración'),
    (81, 'Servicios de ingeniería, investigación y tecnología'),
    (82, 'Servicios editoriales y gráficos'),
    (83, 'Servicios de salud pública'),
    (84, 'Servicios financieros y de seguros'),
    (85, 'Servicios de salud y asistencia social'),
    (86, 'Servicios de educación y formación'),
    (90, 'Servicios de viaje, alimentación y alojamiento'),
    (91, 'Servicios personales y domésticos'),
    (92, 'Defensa, orden público y seguridad'),
    (93, 'Servicios políticos y de asuntos cívicos'),
    (94, 'Organizaciones, asociaciones y afiliaciones'),
    (95, 'Tierras, edificios, estructuras y vías')
)
SELECT c.cod_producto::BIGINT                          AS cod_producto,
       -- LEFT(...): respeta los límites VARCHAR(500)/VARCHAR(255)
       -- del DDL del Paso 1 (algunas desc_linea son más largas)
       LEFT(mp.descripcion_producto, 500)              AS descripcion_producto,
       SUBSTRING(c.cod_producto, 1, 2)::INTEGER        AS segmento,
       s.nombre_segmento,
       SUBSTRING(c.cod_producto, 1, 4)::INTEGER        AS familia,
       NULL::VARCHAR                                   AS nombre_familia,
       SUBSTRING(c.cod_producto, 1, 6)::INTEGER        AS clases,
       NULL::VARCHAR                                   AS nombre_clase,
       SUBSTRING(c.cod_producto, 1, 8)::INTEGER        AS mercancias,
       LEFT(mm.nombre_mercancia, 255)                  AS nombre_mercancia
FROM   codigos c
LEFT JOIN moda_producto  mp ON mp.cod_producto  = c.cod_producto
                           AND mp.rk = 1
LEFT JOIN moda_mercancia mm ON mm.cod_mercancia = SUBSTRING(c.cod_producto, 1, 8)
                           AND mm.rk = 1
LEFT JOIN segmentos      s  ON s.segmento = SUBSTRING(c.cod_producto, 1, 2)::INTEGER;


-- ============================================================
--  VERIFICACIÓN (ejecutar después de la carga)
-- ============================================================

-- 1) Total de productos en el catálogo y % con descripción
-- SELECT COUNT(*)                                        AS total_productos,
--        ROUND(100.0 * COUNT(descripcion_producto) / COUNT(*), 1) AS pct_con_descripcion,
--        ROUND(100.0 * COUNT(nombre_segmento) / COUNT(*), 1)      AS pct_con_segmento
-- FROM dim_catalogo_codigo_identificacion_producto;

-- 2) Cobertura: cod_producto de las tablas de líneas presentes en la dimensión
--    (esperado: 100% — la dimensión se construye de las mismas fuentes)
-- SELECT 'lineas_carteles' AS tabla,
--        ROUND(100.0 * COUNT(d.cod_producto) / NULLIF(COUNT(l.cod_producto), 0), 2) AS pct_match
-- FROM lineas_carteles l
-- LEFT JOIN dim_catalogo_codigo_identificacion_producto d USING (cod_producto)
-- UNION ALL
-- SELECT 'lineas_ofertas',
--        ROUND(100.0 * COUNT(d.cod_producto) / NULLIF(COUNT(l.cod_producto), 0), 2)
-- FROM lineas_ofertas l
-- LEFT JOIN dim_catalogo_codigo_identificacion_producto d USING (cod_producto)
-- UNION ALL
-- SELECT 'lineas_adjudicadas',
--        ROUND(100.0 * COUNT(d.cod_producto) / NULLIF(COUNT(l.cod_producto), 0), 2)
-- FROM lineas_adjudicadas l
-- LEFT JOIN dim_catalogo_codigo_identificacion_producto d USING (cod_producto);

-- 3) Con la dimensión poblada, las FK comentadas del Paso 1
--    (fk_lineas_carteles_producto, etc.) pueden activarse en el futuro
--    si se decide exigir integridad referencial.
