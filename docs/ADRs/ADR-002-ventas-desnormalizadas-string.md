# ADR-002 — Ventas desnormalizadas como string "id_cantidad;..."

- **Estado**: Aceptada
- **Fecha de decisión**: previa a este registro; documentada el 2026-11-07

## Contexto

Al registrar una venta, el frontend envía un arreglo de líneas con `pro_id`, `pro_cantidad` y `pro_subtotal`. El MVP necesitaba persistir la venta en un solo paso, sin crear tablas intermedias ni modificar el esquema de la BD Neon externa (ver ADR-001).

## Decisión

La relación venta↔producto se serializa en la columna `ven_productos` (`varchar(100)`) como pares `id_cantidad` separados por `;` — ejemplo: `5_2;12_1` (producto 5 ×2, producto 12 ×1). `crear_venta` concatena el string y guarda el monto como suma de los `pro_subtotal` del cliente. El reporte diario (`totales_vendidos_por_dia`) **parsea el string en lectura**, reconsulta cada producto y recalcula los montos aplicando ofertas formato `"NxM"` (ver `docs/GLOSARIO.md`).

## Consecuencias

**Positivas**

- Insert trivial: una sola fila, sin FKs ni tabla de detalle.
- El frontend controla el subtotal cobrado en el momento de la venta (monto histórico exacto).

**Negativas**

- **Sin integridad referencial**: un producto borrado deja IDs huérfanos ilegibles en el string.
- Límite de 100 caracteres → pocas líneas por venta.
- El parseo es frágil: un string malformado rompe el reporte diario sin control de errores.
- Lectura N+1 (una query por producto vendido) y recálculo que puede **divergir** de `ven_monto_total` si precios u ofertas cambiaron después de la venta.
- Imposible consultar "ventas de un producto" sin escanear y parsear todas las filas.

**Mitigaciones futuras sugeridas**: tabla normalizada `venta_detalle` (venta, producto, cantidad, precio_unitario_congelado) con FK; migración de datos históricos parseando los strings existentes.