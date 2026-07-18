-- Listado de carteles ganados por Proveedor
/*
SELECT DISTINCT la.nro_sicop,
       lc.nombre_cartel,
       i.nombre_institucion,
       la.monto_adjudicado_linea,
       la.fecha_adjud_firme
FROM lineas_adjudicadas la
JOIN dim_instituciones i
  ON la.cedula_institucion = i.cedula_institucion
LEFT JOIN lineas_carteles lc
  ON la.nro_sicop = lc.nro_sicop
 AND la.nro_linea = lc.nro_linea
WHERE la.cedula_proveedor = '3101005744' --Proveedor de Prueba:Purdy Motors
ORDER BY la.fecha_adjud_firme DESC;
*/

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