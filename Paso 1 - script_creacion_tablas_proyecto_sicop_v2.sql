-- ============================================================
-- Proyecto: Base de datos analítica de compras públicas SICOP
-- Motor: PostgreSQL
-- Descripción:
--   Script para crear las tablas representadas en el modelo
--   suministrado, incluyendo claves primarias, claves foráneas,
--   restricciones básicas e índices de apoyo.
--
-- Nota:
--   Los nombres se normalizan en minúscula y formato snake_case,
--   siguiendo las convenciones habituales de PostgreSQL.
-- ============================================================

-- Opcional: crear la base de datos desde una conexión administrativa.
-- Este bloque debe ejecutarse por separado si se usa una herramienta
-- que no permite cambiar de conexión dentro del mismo script.
-- CREATE DATABASE proyecto_sicop_v1
--     WITH ENCODING = 'UTF8'
--     TEMPLATE = template0;

-- En psql puede descomentarse la siguiente línea después de crearla:
-- \connect proyecto_sicop_v1

BEGIN;
-- ============================================================
-- Creación de tablas "staging"
--   Necesarias para recibir la información de la fuente de datos del observatorio de compra pública.
--   Cada tabla corresponde a un tipo de archivo csv recolectado de la fuente de datos.
-- 	 Estas tablas tendrán los datos que posteriormente serán procesados para popular las tablas creadas anteriormente.
--   El flujo de datos se separa entre:
--    1. Python descarga, extrae y carga en staging mediante COPY.
--    2. PostgreSQL toma los datos desde staging, aplica validaciones, convierte tipos, elimina duplicados y realiza los UPSERT hacia las tablas finales.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE staging.stg_instituciones (
    cedula                  TEXT,
    nombre_institucion      TEXT,
    zona_geo_inst           TEXT,
    fecha_ingreso           TEXT,
	etl_period 				CHAR(6),
	source_file 			VARCHAR(100),
	loaded_at 				TIMESTAMP,
	batch_id 				UUID
);

CREATE TABLE staging.stg_proveedores (
    cedula_proveedor        TEXT,
    nombre_proveedor        TEXT,
    tipo_proveedor          TEXT,
    tamaÑo_proveedor        TEXT,
    fecha_constitucion      TEXT,
    zona_geo_prov           TEXT,
    fecha_registro          TEXT,
	etl_period 				CHAR(6),
	source_file 			VARCHAR(100),
	loaded_at 				TIMESTAMP,
	batch_id 				UUID
);

CREATE TABLE staging.stg_carteles (
    nro_sicop                  	TEXT,
    cedula_institucion         	TEXT,
    fecha_publicacion          	TEXT,
    nro_procedimiento          	TEXT,
    tipo_procedimiento         	TEXT,
    modalidad_procedimiento    	TEXT,
    cartel_stat                	TEXT,
    cartel_nm                  	TEXT,
    fechah_apertura            	TEXT,
    clas_obj                   	TEXT,
    monto_est                  	TEXT,
	etl_period 					CHAR(6),
	source_file 				VARCHAR(100),
	loaded_at 					TIMESTAMP,
	batch_id 					UUID
);

CREATE TABLE staging.stg_lineas_carteles (
    nro_sicop                   TEXT,
    numero_linea                TEXT,
    numero_partida              TEXT,
    cantidad_solicitada         TEXT,
    precio_unitario_estimado    TEXT,
    tipo_moneda                 TEXT,
    tipo_cambio_crc             TEXT,
    codigo_identificacion       TEXT,
    monto_reservado             TEXT,
	desc_linea					TEXT,
	etl_period 					CHAR(6),
	source_file 				VARCHAR(100),
	loaded_at 					TIMESTAMP,
	batch_id 					UUID
);

CREATE TABLE staging.stg_ofertas (
    nro_sicop                  	TEXT,
    nro_oferta                 	TEXT,
    cedula_proveedor           	TEXT,
    fecha_presenta_oferta      	TEXT,
    tipo_oferta                	TEXT,
	etl_period 					CHAR(6),
	source_file 				VARCHAR(100),
	loaded_at 					TIMESTAMP,
	batch_id 					UUID
);

CREATE TABLE staging.stg_lineas_ofertadas (
    nro_sicop                   TEXT,
    nro_oferta                  TEXT,
    nro_linea                   TEXT,
    codigo_producto_cl          TEXT,
    cantidad_ofertada           TEXT,
    precio_unitario_ofertado    TEXT,
    tipo_moneda                 TEXT,
    tipo_cambio_crc             TEXT,
	etl_period 					CHAR(6),
	source_file 				VARCHAR(100),
	loaded_at 					TIMESTAMP,
	batch_id 					UUID
);

CREATE TABLE staging.stg_procedimientos_adjudicacion (
    nro_sicop                 	TEXT,
    cedula                    	TEXT,
    numero_procedimiento      	TEXT,
    descr_procedimiento       	TEXT,
    linea                     	TEXT,
    prod_id                   	TEXT,
    fecha_adjud_firme         	TEXT,
    monto_adju_linea          	TEXT,
	etl_period 					CHAR(6),
	source_file 				VARCHAR(100),
	loaded_at 					TIMESTAMP,
	batch_id 					UUID
);

CREATE TABLE staging.stg_lineas_adjudicadas (
    nro_sicop                      	TEXT,
    nro_oferta                     	TEXT,
    nro_linea                      	TEXT,
	codigo_producto					TEXT,
    cedula_proveedor               	TEXT,
    cantidad_adjudicada            	TEXT,
    precio_unitario_adjudicado     	TEXT,
    iva                            	TEXT,
    otros_impuestos                	TEXT,
    acarreos                       	TEXT,
    tipo_moneda                    	TEXT,
    tipo_cambio_crc                	TEXT,
	etl_period 						CHAR(6),
	source_file 					VARCHAR(100),
	loaded_at 						TIMESTAMP,
	batch_id 						UUID
);


-- ============================================================
-- Tabla: dim_proveedores
-- Descripción:
--   Almacena la información maestra de los proveedores registrados
--   en SICOP. Cada proveedor se identifica de manera única mediante
--   su número de cédula y puede relacionarse con ofertas y líneas
--   adjudicadas.
-- Fuente original: Proveedores.csv
-- ============================================================
CREATE TABLE dim_proveedores (
    cedula_proveedor  VARCHAR(30)  PRIMARY KEY,
    nombre_proveedor  VARCHAR(255) NOT NULL,
    tipo_proveedor    VARCHAR(100),
    tamano            VARCHAR(100),
    provincia         VARCHAR(50),
    canton            VARCHAR(50),
    distrito          VARCHAR(50)
);

-- ============================================================
-- Tabla: dim_instituciones
-- Descripción:
--   Contiene el catálogo de instituciones públicas compradoras.
--   La cédula institucional funciona como identificador único y
--   permite asociar las instituciones con carteles y adjudicaciones.
-- Fuente original: InstitucionesRegistradas.csv
-- ============================================================
CREATE TABLE dim_instituciones (
    cedula_institucion  VARCHAR(30)  PRIMARY KEY,
    nombre_institucion  VARCHAR(255) NOT NULL,
    provincia           VARCHAR(100),
    canton              VARCHAR(100),
    distrito            VARCHAR(100)
);

-- ============================================================
-- Tabla: dim_catalogo_codigo_identificacion_producto
-- Descripción:
--   Mantiene la clasificación jerárquica de productos utilizada por
--   SICOP. Incluye segmento, familia, clase y mercancía para cada
--   código de producto.
-- Fuente original: SICOP
-- ============================================================
CREATE TABLE dim_catalogo_codigo_identificacion_producto (
    cod_producto          BIGINT      PRIMARY KEY,
    descripcion_producto  VARCHAR(500),
    segmento              INTEGER,
    nombre_segmento       VARCHAR(255),
    familia               INTEGER,
    clases                INTEGER,
    mercancias            INTEGER,
    nombre_mercancia      VARCHAR(255)
);

-- ============================================================
-- Tabla: lineas_carteles
-- Descripción:
--   Almacena las líneas publicadas en los carteles o procedimientos
--   de contratación. Cada línea contiene el producto solicitado,
--   cantidades, montos estimados, moneda, institución compradora y
--   datos generales del procedimiento.
-- Fuentes originales: DetalleCarteles.csv y DetalleLineaCartel.csv
-- ============================================================
CREATE TABLE lineas_carteles (
    nro_sicop                  VARCHAR(100) NOT NULL,
    nro_procedimiento          VARCHAR(100),
    nro_sicop_nro_linea        VARCHAR(160),
    nombre_cartel              VARCHAR(500),
    status_cartel              VARCHAR(100),
    clasificacion_cartel       VARCHAR(150),
    monto_estimado_cartel_crc  NUMERIC(18, 4),
    nro_linea                  INTEGER      NOT NULL,
    nro_partida                INTEGER,
    cod_producto               BIGINT,
    cantidad                   NUMERIC(18, 4),
    precio_unitario_estimado   NUMERIC(18, 4),
    monto_total_linea_estimado NUMERIC(18, 4),
    tipo_moneda                VARCHAR(30),
    tipo_cambio_crc            NUMERIC(18, 6),
    cedula_institucion         VARCHAR(30),
    tipo_procedimiento         VARCHAR(150),
    modalidad_procedimiento    VARCHAR(150),
    fecha_publicacion          TIMESTAMP,
    fecha_apertura             TIMESTAMP,

    CONSTRAINT pk_lineas_carteles
        PRIMARY KEY (nro_sicop, nro_linea),

    CONSTRAINT uq_lineas_carteles_compuesto
        UNIQUE (nro_sicop_nro_linea),

    CONSTRAINT fk_lineas_carteles_producto
        FOREIGN KEY (cod_producto)
        REFERENCES dim_catalogo_codigo_identificacion_producto (cod_producto)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_lineas_carteles_institucion
        FOREIGN KEY (cedula_institucion)
        REFERENCES dim_instituciones (cedula_institucion)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT ck_lineas_carteles_cantidad
        CHECK (cantidad IS NULL OR cantidad >= 0),

    CONSTRAINT ck_lineas_carteles_montos
        CHECK (
            (precio_unitario_estimado IS NULL OR precio_unitario_estimado >= 0)
            AND
            (monto_total_linea_estimado IS NULL OR monto_total_linea_estimado >= 0)
            AND
            (monto_estimado_cartel_crc IS NULL OR monto_estimado_cartel_crc >= 0)
        )
);


-- ============================================================
-- Tabla: lineas_ofertas
-- Descripción:
--   Registra el detalle de los productos y precios ofrecidos por cada
--   proveedor para una línea específica de un procedimiento de contratación.
--   Se relaciona con el encabezado de la oferta, la línea del cartel y
--   el catálogo de productos.
-- Fuente original: LineasOfertadas.csv
-- ============================================================
CREATE TABLE lineas_ofertas (
    nro_oferta_nro_linea     VARCHAR(160),
	cedula_proveedor         VARCHAR(30),
    fecha_oferta_presentada  TIMESTAMP,
    tipo_oferta              VARCHAR(100),
    nro_oferta               VARCHAR(100) NOT NULL,
    cod_producto             BIGINT,
    nro_sicop                VARCHAR(100) NOT NULL,
    nro_linea                INTEGER      NOT NULL,
    nro_sicop_nro_linea      VARCHAR(160),
    cantidad_ofertada        NUMERIC(18, 4),
    precio_unitario_ofertado NUMERIC(18, 4),
    tipo_moneda              VARCHAR(30),
    tipo_cambio_crc          NUMERIC(18, 6),

    CONSTRAINT pk_lineas_ofertas
        PRIMARY KEY (nro_sicop, nro_oferta, nro_linea),

    CONSTRAINT uq_lineas_ofertas_compuesto
        UNIQUE (nro_oferta_nro_linea),

    CONSTRAINT fk_lineas_ofertas_proveedor
        FOREIGN KEY (cedula_proveedor)
        REFERENCES dim_proveedores (cedula_proveedor)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_lineas_ofertas_producto
        FOREIGN KEY (cod_producto)
        REFERENCES dim_catalogo_codigo_identificacion_producto (cod_producto)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT ck_lineas_ofertas_cantidad
        CHECK (cantidad_ofertada IS NULL OR cantidad_ofertada >= 0),

    CONSTRAINT ck_lineas_ofertas_precio
        CHECK (precio_unitario_ofertado IS NULL OR precio_unitario_ofertado >= 0)
);

-- ============================================================
-- Tabla: lineas_adjudicadas
-- Descripción:
--   Contiene el resultado de las adjudicaciones por línea y oferta.
--   Guarda las cantidades, precios, montos adjudicados, proveedor,
--   institución, producto y fechas asociadas al acto de adjudicación.
-- Fuente original: datos de adjudicaciones de SICOP
-- ============================================================
CREATE TABLE lineas_adjudicadas (
    nro_sicop_nro_linea       VARCHAR(160),
    nro_sicop                 VARCHAR(100) NOT NULL,
    nro_oferta                VARCHAR(100) NOT NULL,
    nro_procedimiento         VARCHAR(100),
    nro_linea                 INTEGER      NOT NULL,
    descr_procedimiento       VARCHAR(500),
    cantidad_adjudicada       NUMERIC(18, 4),
    precio_unitario_adjudicado NUMERIC(18, 4),
    monto_adjudicado_linea    NUMERIC(18, 4),
    cedula_institucion        VARCHAR(30),
    fecha_adjud_firme         DATE,
    cedula_proveedor          VARCHAR(30)  NOT NULL,
    cod_producto              BIGINT,
    moneda_adjudicada         VARCHAR(30),
    tipo_cambio_crc           NUMERIC(18, 6),

    CONSTRAINT pk_lineas_adjudicadas
        PRIMARY KEY (nro_sicop, nro_oferta, nro_linea),

    CONSTRAINT fk_lineas_adjudicadas_linea_oferta
        FOREIGN KEY (nro_sicop, nro_oferta, nro_linea)
        REFERENCES lineas_ofertas (nro_sicop, nro_oferta, nro_linea)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_lineas_adjudicadas_institucion
        FOREIGN KEY (cedula_institucion)
        REFERENCES dim_instituciones (cedula_institucion)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_lineas_adjudicadas_proveedor
        FOREIGN KEY (cedula_proveedor)
        REFERENCES dim_proveedores (cedula_proveedor)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_lineas_adjudicadas_producto
        FOREIGN KEY (cod_producto)
        REFERENCES dim_catalogo_codigo_identificacion_producto (cod_producto)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT ck_lineas_adjudicadas_cantidad
        CHECK (cantidad_adjudicada IS NULL OR cantidad_adjudicada >= 0),

    CONSTRAINT ck_lineas_adjudicadas_montos
        CHECK (
            (precio_unitario_adjudicado IS NULL OR precio_unitario_adjudicado >= 0)
            AND
            (monto_adjudicado_linea IS NULL OR monto_adjudicado_linea >= 0)
        )
);

-- ============================================================
-- Índices adicionales
-- Descripción:
--   Mejoran las consultas y uniones frecuentes por claves foráneas,
--   institución, proveedor, producto y procedimiento.
-- ============================================================

CREATE INDEX idx_lineas_carteles_cod_producto
    ON lineas_carteles (cod_producto);

CREATE INDEX idx_lineas_carteles_cedula_institucion
    ON lineas_carteles (cedula_institucion);

CREATE INDEX idx_lineas_carteles_nro_procedimiento
    ON lineas_carteles (nro_procedimiento);

CREATE INDEX idx_lineas_ofertas_cod_producto
    ON lineas_ofertas (cod_producto);

CREATE INDEX idx_lineas_adjudicadas_cedula_proveedor
    ON lineas_adjudicadas (cedula_proveedor);

CREATE INDEX idx_lineas_adjudicadas_cedula_institucion
    ON lineas_adjudicadas (cedula_institucion);

CREATE INDEX idx_lineas_adjudicadas_cod_producto
    ON lineas_adjudicadas (cod_producto);

CREATE INDEX idx_lineas_adjudicadas_nro_procedimiento
    ON lineas_adjudicadas (nro_procedimiento);

COMMIT;
