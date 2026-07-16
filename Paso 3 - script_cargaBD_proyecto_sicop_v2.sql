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
