# GLOSARIO — Proyecto "inventario"

Lenguaje ubicuo del dominio. Fuente de verdad de terminología para analistas, desarrollo y revisión de código. Registrado el 2026-11-07 a partir de `models.py` y `views.py`.

## Entidades del dominio

| Término | Modelo (tabla) | Definición | Campos clave |
|---|---|---|---|
| **Dueño** | `Dueno` (`dueno`) | Propietario de los productos. El negocio tiene tres: **Mireya (id 1), Ivan (id 2), Paulina (id 3)** | `due_id`, `due_nombre`, `due_estado` (bool) |
| **Tipo** | `Tipo` (`tipo`) | Categoría del producto: **Ropa (1), Paquetería (2), Útiles escolares (3)** | `tip_id`, `tip_nombre` |
| **Ubicación** | `Ubicacion` (`ubicacion`) | Lugar físico donde se almacena un producto | `ubi_id`, `ubi_nombre` |
| **Producto** | `Productos` (`productos`) | Artículo del inventario. Tiene un código único de 8 dígitos, precio unitario, cantidad en stock y oferta opcional; se asocia a una ubicación, un dueño y un tipo | `pro_id`, `pro_nombre`, `pro_codigo`, `pro_precio`, `pro_cantidad`, `pro_precio_oferta`, `pro_estado` (int, se crea con valor 1), FKs `pro_ubicacion`, `pro_dueno`, `pro_tipo` |
| **Usuario** | `Usuarios` (`usuarios`) | Operador del sistema que inicia sesión con RUT y clave | `usu_id`, `usu_rut` (único), `usu_clave` (**texto plano**), `usu_nombre`, `usu_estado` (bool) |
| **Venta** | `Ventas` (`ventas`) | Transacción realizada en un puesto. Guarda fecha de registro, monto total y los productos vendidos **serializados como string** | `ven_id`, `ven_fecha_registro`, `ven_productos`, `ven_monto_total`, `ven_puesto` (int, referencia lógica a `Puestos`, sin FK) |
| **Puesto** | `Puestos` (`puestos`) | Punto de venta físico (mesa/stand) donde se realiza la transacción | `pue_id`, `pue_nombre` |

## Términos de negocio

- **Oferta "2x1500"** — formato de promoción almacenado en `pro_precio_oferta`: `"NxM"` significa *N unidades por M de precio total*. Ejemplo: `2x1500` = 2 unidades cuestan 1500 en total. Si se venden más unidades que el grupo de oferta, se cobra por grupos completos más unidades sueltas a precio normal: 5 unidades con oferta `2x1500` y precio normal `1000` → (2 grupos × 1500) + (1 × 1000) = **4000**. Este recálculo lo hace `totales_vendidos_por_dia`; `crear_producto` guarda el valor **sin espacios**.
- **Código de producto** — cadena de **8 dígitos** (`pro_codigo`) que identifica al producto. En `crear_producto`: si no se envía o ya existe, se genera uno aleatorio y se verifica contra la BD hasta lograr unicidad.
- **Puesto** — punto de venta físico. La venta lo registra como entero (`ven_puesto`), **sin clave foránea**.
- **Reporte diario** — salida de `totales_vendidos_por_dia`: total vendido del día, desglose por dueño (Mireya/Ivan/Paulina) y por tipo (Ropa/Paquetería/Útiles), y detalle de productos vendidos con montos recalculados según ofertas.
- **Keep-alive ("estoy vivo")** — tráfico periódico que evita que Render duerma el servicio del free tier. Implementado como bucle in-request en `/api/estoy_vivo/` (ver ADR-004).

## Formato del campo `ven_productos`

Columna `varchar(100)` que contiene pares `id_cantidad` separados por `;`:

```
5_2;12_1;7_3
```

| Par | Significado |
|---|---|
| `5_2`  | producto con `pro_id=5`, cantidad vendida: 2 |
| `12_1` | producto con `pro_id=12`, cantidad vendida: 1 |
| `7_3`  | producto con `pro_id=7`, cantidad vendida: 3 |

Reglas del formato:

- No hay FK ni tabla intermedia: la relación venta↔producto **solo existe en este string** (ADR-002).
- `crear_venta` lo genera concatenando lo que envía el cliente; `totales_vendidos_por_dia` lo parsea con `split(";")` y `split("_")` — un string malformado rompe el reporte.
- El límite de 100 caracteres restringe la cantidad de líneas por venta.

## Convenciones de IDs hardcodeados en el código

| ID | Significado | Dónde se asume |
|---|---|---|
| `dueno` = 1 / 2 / 3 | Mireya / Ivan / Paulina | `totales_vendidos_por_dia` (distribución por dueño) |
| `tipo` = 1 / 2 / 3 | Ropa / Paquetería / Útiles escolares | `totales_vendidos_por_dia` y `estoy_vivo` (filtra tipo 1) |
| `ubicacion` = 1 | Única ubicación consultada | `listar_productos` (filtro fijo `pro_ubicacion=1`) |

> ⚠️ Cambiar los catálogos en la base de datos sin actualizar el código **romperá los reportes y listados**. Ver el riesgo R8 en [`ARQUITECTURA.md`](ARQUITECTURA.md).