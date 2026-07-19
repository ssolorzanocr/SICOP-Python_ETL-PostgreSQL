-- ===================================================================
-- Consulta para ingresar los datos en la tabla de proveedores
INSERT INTO dim_proveedores
(
    cedula_proveedor,
    nombre_proveedor,
	tipo_proveedor,
	tamano,
    distrito,
    canton,
    provincia
)

SELECT DISTINCT ON (stg_proveedores.cedula_proveedor)
    stg_proveedores.cedula_proveedor,
    stg_proveedores.nombre_proveedor,
	stg_proveedores.tipo_proveedor,
	stg_proveedores.tamaÑo_proveedor,
    NULLIF(TRIM(split_part(zona_geo_prov, ',', 1)), '') AS distrito,
    NULLIF(TRIM(split_part(zona_geo_prov, ',', 2)), '') AS canton,
    NULLIF(TRIM(split_part(zona_geo_prov, ',', 3)), '') AS provincia

FROM staging.stg_proveedores

ORDER BY
    stg_proveedores.cedula_proveedor,
    stg_proveedores.loaded_at DESC;

-- ===================================================================
-- Consulta para ingresar los datos en la tabla de instituciones

INSERT INTO dim_instituciones
(
    cedula_institucion,
    nombre_institucion,
    distrito,
    canton,
    provincia
)

SELECT DISTINCT ON (cedula)
    cedula,
    nombre_institucion,
    NULLIF(TRIM(split_part(zona_geo_inst, ',', 1)), '') AS distrito,
    NULLIF(TRIM(split_part(zona_geo_inst, ',', 2)), '') AS canton,
    NULLIF(TRIM(split_part(zona_geo_inst, ',', 3)), '') AS provincia

FROM staging.stg_instituciones

ORDER BY
    cedula,
    loaded_at DESC;

-- ============================================================
--  Consulta para la carga de dim_catalogo_codigo_identificacion_producto
--    Reconstruye el catálogo completo directamente desde el staging
--    ya cargado por el Paso 2 — no requiere archivos adicionales.
--
--  ESTRUCTURA DEL CÓDIGO DE PRODUCTO (16 dígitos, basado en UNSPSC):
--    Dígitos 1-2  → Segmento
--    Dígitos 1-4  → Familia
--    Dígitos 1-6  → Clase
--    Dígitos 1-8  → Mercancía
--    Dígitos 9-16 → ID interno SICOP del producto
--    - nombre_segmento proviene de un lookup embebido (57 segmentos
--      UNSPSC.
--    - nombre_familia y nombre_clase quedan NULL: ya que SICOP no publica
--      esos nombres en los CSV del observatorio.
--    - nombre_mercancia = descripción más frecuente entre los
--      productos que comparten el mismo artículo de 8 dígitos.

INSERT INTO dim_catalogo_codigo_identificacion_producto (
    cod_producto,
    descripcion_producto,
    segmento,
    nombre_segmento,
    familia,
    clases,
    mercancias,
    nombre_mercancia
)
WITH codigos_crudos AS (
    -- Unión de todas las fuentes de código de producto en staging.
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
       SUBSTRING(c.cod_producto, 1, 6)::INTEGER        AS clases,
       SUBSTRING(c.cod_producto, 1, 8)::INTEGER        AS mercancias,
       LEFT(mm.nombre_mercancia, 255)                  AS nombre_mercancia
FROM   codigos c
LEFT JOIN moda_producto  mp ON mp.cod_producto  = c.cod_producto
                           AND mp.rk = 1
LEFT JOIN moda_mercancia mm ON mm.cod_mercancia = SUBSTRING(c.cod_producto, 1, 8)
                           AND mm.rk = 1
LEFT JOIN segmentos      s  ON s.segmento = SUBSTRING(c.cod_producto, 1, 2)::INTEGER;


-- ===================================================================
-- Consulta para ingresar los datos en la tabla de lineas carteles
INSERT INTO lineas_carteles
(
    nro_sicop,
    nro_procedimiento,
    nro_sicop_nro_linea,
    nombre_cartel,
    status_cartel,
    clasificacion_cartel,
    monto_estimado_cartel_crc,
    nro_linea,
    nro_partida,
    cod_producto,
    cantidad,
    precio_unitario_estimado,
    monto_total_linea_estimado,
    tipo_moneda,
    tipo_cambio_crc,
    cedula_institucion,
    tipo_procedimiento,
    modalidad_procedimiento,
    fecha_publicacion,
    fecha_apertura
)

WITH carteles AS -- tomamos la fila más actualizada para eliminar registros duplicados de carteles.
(
    SELECT *
    FROM
    (
        SELECT
            *,
            ROW_NUMBER() OVER
            (
                PARTITION BY nro_sicop
                ORDER BY
                    etl_period DESC,
                    loaded_at DESC
            ) AS rn
        FROM staging.stg_carteles
    ) t
    WHERE rn = 1
),

lineas AS -- repetimos el proceso para tomar la linea de cartel más actualizada y eliminar registros duplicados.
(
    SELECT *
    FROM
    (
        SELECT
            *,
            ROW_NUMBER() OVER
            (
                PARTITION BY
                    nro_sicop,
                    numero_linea,
                    codigo_identificacion
                ORDER BY
                    etl_period DESC,
                    loaded_at DESC
            ) AS rn
        FROM staging.stg_lineas_carteles
    ) t
    WHERE rn = 1
)

SELECT
    l.nro_sicop,
    c.nro_procedimiento,
    CONCAT(l.nro_sicop,'_',l.numero_linea) AS nro_sicop_nro_linea,
    LEFT(c.cartel_nm,500),
    c.cartel_stat,
    c.clas_obj,
    NULLIF(c.monto_est,'')::NUMERIC(18,4),
    NULLIF(l.numero_linea,'')::INTEGER,
    NULLIF(l.numero_partida,'')::INTEGER,
    NULLIF(SUBSTRING(TRIM(l.codigo_identificacion),1,16),'')::BIGINT,
    NULLIF(l.cantidad_solicitada,'')::NUMERIC(18,4),
    NULLIF(l.precio_unitario_estimado,'')::NUMERIC(18,4),
    NULLIF(l.monto_reservado,'')::NUMERIC(18,4),
    l.tipo_moneda,
    NULLIF(l.tipo_cambio_crc,'')::NUMERIC(18,6),
    c.cedula_institucion,
    c.tipo_procedimiento,
    c.modalidad_procedimiento,
    TO_DATE(SUBSTRING(c.fecha_publicacion,1,19),'YYYY-MM-DD HH24:MI:SS'),
    TO_DATE(SUBSTRING(c.fechah_apertura,1,19),'YYYY-MM-DD HH24:MI:SS')

FROM lineas l LEFT JOIN carteles c
ON l.nro_sicop = c.nro_sicop;


-- ===================================================================
-- Consulta para ingresar los datos en la tabla de lineas ofertas
INSERT INTO lineas_ofertas
(
    nro_oferta_nro_linea,
    cedula_proveedor,
    fecha_oferta_presentada,
    tipo_oferta,
    nro_oferta,
    cod_producto,
    nro_sicop,
    nro_linea,
    nro_sicop_nro_linea,
    cantidad_ofertada,
    precio_unitario_ofertado,
    tipo_moneda,
    tipo_cambio_crc
)

WITH ofertas AS -- tomamos la fila más actualizada para eliminar registros duplicados de ofertada.
(
    SELECT *
    FROM
    (
        SELECT
            *,
            ROW_NUMBER() OVER
            (
                PARTITION BY nro_oferta
                ORDER BY
                    etl_period DESC,
                    loaded_at DESC
            ) AS rn
        FROM staging.stg_ofertas
    ) t
    WHERE rn = 1
),

lineas AS -- tomamos la fila más actualizada para eliminar registros duplicados de líneas ofertadas.
(
    SELECT *
    FROM
    (
        SELECT
            *,
            ROW_NUMBER() OVER
            (
                PARTITION BY
                    nro_oferta,
                    nro_linea,
                    codigo_producto_cl
                ORDER BY
                    etl_period DESC,
                    loaded_at DESC
            ) AS rn
        FROM staging.stg_lineas_ofertadas
    ) t
    WHERE rn = 1
)

SELECT
    CONCAT(l.nro_oferta,'_',l.nro_linea)                    AS nro_oferta_nro_linea,
    o.cedula_proveedor,
    TO_DATE(o.fecha_presenta_oferta,'YYYY-MM-DD HH24:MI:SS') AS fecha_oferta_presentada,
    o.tipo_oferta,
    l.nro_oferta,
    NULLIF(TRIM(l.codigo_producto_cl),'')::BIGINT           AS cod_producto,
    l.nro_sicop,
    NULLIF(l.nro_linea,'')::INTEGER,
    CONCAT(l.nro_sicop,'_',l.nro_linea)                     AS nro_sicop_nro_linea,
    NULLIF(l.cantidad_ofertada,'')::NUMERIC(18,4),
    NULLIF(l.precio_unitario_ofertado,'')::NUMERIC(18,4),
    l.tipo_moneda,
    NULLIF(l.tipo_cambio_crc,'')::NUMERIC(18,6)

FROM lineas l LEFT JOIN ofertas o
ON l.nro_oferta = o.nro_oferta;


-- ===================================================================
-- Consulta para ingresar los datos en la tabla de lineas adjudicadas
INSERT INTO lineas_adjudicadas
(
    nro_sicop_nro_linea,
    nro_sicop,
    nro_oferta,
    nro_procedimiento,
    nro_linea,
    descr_procedimiento,
    cantidad_adjudicada,
    precio_unitario_adjudicado,
    monto_adjudicado_linea,
    cedula_institucion,
    fecha_adjud_firme,
    cedula_proveedor,
    cod_producto,
    moneda_adjudicada,
    tipo_cambio_crc
)

WITH lineas AS -- tomamos la fila más actualizada para eliminar registros duplicados de líneas adjudicadas.
(
    SELECT *
    FROM
    (
        SELECT
            *,
            ROW_NUMBER() OVER
            (
                PARTITION BY
                    staging.stg_lineas_adjudicadas.nro_sicop,
                    staging.stg_lineas_adjudicadas.nro_oferta,
                    staging.stg_lineas_adjudicadas.nro_linea,
                    staging.stg_lineas_adjudicadas.codigo_producto
                ORDER BY
                    staging.stg_lineas_adjudicadas.etl_period DESC,
                    staging.stg_lineas_adjudicadas.loaded_at DESC
            ) rn

        FROM staging.stg_lineas_adjudicadas
    ) t
    WHERE rn = 1
),

procedimientos AS -- repetimos el proceso para tomar la fila de procedimiento más actualizada para eliminar registros duplicados.
(
    SELECT *
    FROM
    (
        SELECT
            *,
            ROW_NUMBER() OVER
            (
                PARTITION BY
                    staging.stg_procedimientos_adjudicacion.nro_sicop,
                    staging.stg_procedimientos_adjudicacion.linea,
                    staging.stg_procedimientos_adjudicacion.prod_id

                ORDER BY
                    staging.stg_procedimientos_adjudicacion.etl_period DESC,
                    staging.stg_procedimientos_adjudicacion.loaded_at DESC
            ) rn
        FROM staging.stg_procedimientos_adjudicacion
    ) t
    WHERE rn = 1
)

SELECT
    CONCAT(l.nro_sicop,'_',l.nro_linea) AS nro_sicop_nro_linea,
    l.nro_sicop,
    l.nro_oferta,
    p.numero_procedimiento,
    NULLIF(l.nro_linea,'')::INTEGER,
    LEFT(p.descr_procedimiento,500),
    NULLIF(l.cantidad_adjudicada,'')::NUMERIC(18,4),
    NULLIF(l.precio_unitario_adjudicado,'')::NUMERIC(18,4),
    NULLIF(p.monto_adju_linea,'')::NUMERIC(18,4),
    p.cedula,
    TO_DATE(p.fecha_adjud_firme,'DD/MM/YYYY'),
    l.cedula_proveedor,
    NULLIF(TRIM(p.prod_id),'')::BIGINT,
    l.tipo_moneda,
    NULLIF(l.tipo_cambio_crc,'')::NUMERIC(18,6)

FROM lineas l LEFT JOIN procedimientos p
    ON l.nro_sicop = p.nro_sicop
   AND l.nro_linea = p.linea
   AND SUBSTRING(TRIM(l.codigo_producto),1,16) = TRIM(p.prod_id);
