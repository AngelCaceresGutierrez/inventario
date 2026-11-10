# Inventario — API REST de gestión de inventario y ventas

API REST construida con **Django 5.2 + Django REST Framework** para administrar el inventario y las ventas de un negocio con productos de tres dueños (**Mireya**, **Ivan** y **Paulina**). Los productos se clasifican por **tipo** (Ropa, Paquetería, Útiles escolares), **ubicación física** y se venden en distintos **puestos** de venta.

- **URL desplegada**: https://inventario-mzod.onrender.com (Render, free tier)
- **Base de datos**: PostgreSQL administrado en **Neon Tech** (externa, creada fuera de Django)
- **Consumidores**: SPA frontend externa (este repo NO incluye frontend)

> ⚠️ **ADVERTENCIA DE SEGURIDAD — LEER ANTES DE USAR**
> Este repositorio expone credenciales reales: la contraseña de la base de datos Neon y la `SECRET_KEY` de Django están **hardcodeadas como valores por defecto** en `inventario/settings.py`, y el repo es público. Además, en producción corren `DEBUG=True`, `ALLOWED_HOSTS=['*']` y `CORS_ALLOW_ALL_ORIGINS=True`; la autenticación compara contraseñas en **texto plano**; el endpoint `editar_producto` acepta actualizar **cualquier columna** (mass assignment) y casi todos los endpoints funcionan **sin autenticación**. **Si esta base contiene datos reales: rotar credenciales URGENTEMENTE.** Detalle completo en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md), sección "Deuda técnica y riesgos".

## Stack

| Componente | Tecnología | Versión |
|---|---|---|
| Framework web | Django | 5.2.3 |
| API REST | Django REST Framework | 3.16.0 |
| Base de datos | PostgreSQL (Neon Tech, externa) | — |
| Driver BD | psycopg2-binary | 2.9.10 |
| CORS | django-cors-headers | 4.7.0 |
| Configuración | python-decouple | 3.8 |
| Servidor de aplicación | gunicorn | 21.2.0 |
| Archivos estáticos | whitenoise | 6.6.0 (instalado; middleware comentado) |
| Cliente HTTP | requests | (usado por el keep-alive) |

## Estructura del proyecto

```
inventario/
├── inventario/            # Configuración del proyecto Django
│   ├── settings.py        # Configuración global (BD, CORS, apps)
│   ├── urls.py            # Rutas raíz (incluye api/)
│   ├── wsgi.py / asgi.py
├── api_inventario/        # Única app: toda la lógica de negocio
│   ├── models.py          # 7 modelos UNMANAGED (mapean la BD externa de Neon)
│   ├── views.py           # Vistas funcionales @api_view (sin ViewSets ni serializers)
│   ├── urls.py            # Rutas bajo /api/
│   ├── admin.py           # Vacío
│   └── tests.py           # Vacío (sin tests)
├── manage.py
└── requirements.txt
```

## Cómo correr localmente

### 1. Requisitos

- Python 3.11+ 
- Acceso de red a la BD Neon (host `ep-still-thunder-...neon.tech`, conexión con SSL obligatoria `sslmode=require`)

### 2. Entorno virtual e instalación

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Variables de entorno (archivo `.env` en la raíz, leído con python-decouple)

```env
SECRET_KEY=una-clave-secreta-segura
DB_NAME=neondb
DB_USER=neondb_owner
DB_PASSWORD=<contraseña de Neon — NUNCA versionarla>
DB_HOST=ep-still-thunder-a290hr9x-pooler.eu-central-1.aws.neon.tech
DB_PORT=5432
```

> ⚠️ `settings.py` tiene todos estos valores como **defaults hardcodeados** (incluida la contraseña real). Si una variable falta en `.env`, se usará el default. La conexión usa `sslmode=require` fijo en el código.

### 4. Levantar el servidor

```bash
python manage.py runserver
```

La API queda disponible en `http://127.0.0.1:8000/api/...`

> **Nota**: ejecutar `manage.py migrate` no tiene efecto: los modelos son `managed=False` y las tablas ya existen en Neon (ver ADR-001).

## Endpoints

Todas las rutas viven bajo el prefijo **`/api/`** (definidas en `api_inventario/urls.py`).

| Ruta | Método | Parámetros | Respuesta exitosa (200) | Notas |
|---|---|---|---|---|
| `/api/estoy_vivo/` | GET | — | `[{"pro_id": n}, ...]` (productos de tipo 1) | Keep-alive. **Bloquea un worker ~8 minutos** y luego se auto-llama para mantener el servicio despierto (ADR-004) |
| `/api/traer_usuarios/` | GET | — | `[{"usu_id", "usu_rut", "usu_nombre"}, ...]` | Expone los RUTs. Sin autenticación |
| `/api/iniciar_sesion/` | POST | body JSON: `usu_rut`, `usu_clave` | `{"message": "Inicio de sesión exitoso", "usuario_id": n}` | Compara la clave en **texto plano**. Credenciales inválidas → 400 |
| `/api/listar_productos/` | GET | query: `buscar` (código exacto o nombre parcial) | `{"productos": [{pro_id, pro_nombre, pro_precio, pro_precio_oferta, tipo, ubicacion, codigo, cantidad, dueno}]}` | Filtra **siempre por ubicación 1** (hardcode). **Bug: si no se envía `buscar` lanza `UnboundLocalError` (500)** |
| `/api/productos_por_tipo/` | GET | query: `tipo` (id numérico, opcional) | `{"productos": [{pro_id, pro_nombre, pro_precio, pro_precio_oferta, pro_codigo}]}` | Sin `tipo` devuelve todos los productos |
| `/api/traer_categorias/` | GET | — | `{"ubicacion": [...], "dueno": [...], "tipo": [...]}` | Catálogos para los combos del frontend |
| `/api/crear_producto/` | POST | body JSON: `nombre`, `cantidad`, `codigo`, `precio`, `precio_oferta`, `tipo`, `ubicacion`, `dueno` | `{"message", "producto": {id, nombre, codigo, cantidad, precio}}` | Si `codigo` falta o está duplicado se genera uno aleatorio de 8 dígitos. `precio_oferta` en formato `"2x1500"` (se le quitan espacios) |
| `/api/editar_producto/` | PATCH | body JSON: `id`, `prod` = objeto `{campo: valor, ...}` | `{"message": "Producto editado exitosamente"}` | Ejecuta `update(**prod)`: **acepta cualquier columna** del modelo (mass assignment), sin whitelist |
| `/api/crear_venta/` | POST | body JSON: `arr` = `[{pro_id, pro_cantidad, pro_subtotal, ..., puesto}]` | `{"message": "Venta creada exitosamente"}` | Suma los `pro_subtotal` tal cual los envía el cliente; serializa los productos como `"id_cantidad;id_cantidad"`. El `puesto` se lee del **último** elemento del array (acoplamiento frágil) |
| `/api/totales_vendidos_por_dia/` | GET | query: `fecha=YYYY-MM-DD` (opcional; por defecto hoy) | `{"respuesta": {fecha, total_vendido, vendido_mireya, vendido_ivan, vendido_paulina, vendido_ropa, vendido_paqueteria, vendido_utiles, productos[]}}` | Parsea `ven_productos` y **recalcula los montos** aplicando ofertas. IDs de dueños/tipos hardcodeados (ver `docs/GLOSARIO.md`) |

### Ejemplos rápidos

```bash
# Login
curl -X POST https://inventario-mzod.onrender.com/api/iniciar_sesion/ \
  -H "Content-Type: application/json" \
  -d "{\"usu_rut\": \"12.345.678-9\", \"usu_clave\": \"secreta\"}"

# Crear venta (el ÚLTIMO elemento del array debe llevar la clave "puesto")
curl -X POST https://inventario-mzod.onrender.com/api/crear_venta/ \
  -H "Content-Type: application/json" \
  -d "{\"arr\":[{\"pro_id\":1,\"pro_cantidad\":2,\"pro_subtotal\":3000,\"puesto\":1},{\"pro_id\":5,\"pro_cantidad\":1,\"pro_subtotal\":1500,\"puesto\":1}]}"

# Reporte del día
curl "https://inventario-mzod.onrender.com/api/totales_vendidos_por_dia/?fecha=2026-11-07"
```

## Despliegue (Render)

- **Plataforma**: Render — servicio web en **free tier**, URL `https://inventario-mzod.onrender.com`.
- **Servidor**: gunicorn sobre `inventario.wsgi`.
- **Sleep del free tier**: Render duerme el servicio tras ~15 minutos sin tráfico. El endpoint `/api/estoy_vivo/` implementa un **keep-alive auto-sostenido** (bucle in-request de 8 minutos) para evitarlo — ver ADR-004.
- Las variables de entorno pueden definirse en el dashboard de Render; **hoy el código usa defaults hardcodeados**, por lo que "funciona" incluso sin configurarlas (riesgo grave).
- whitenoise está instalado pero su middleware está comentado: este repo no sirve ningún frontend.

## Seguridad (resumen)

1. **Credenciales de la BD Neon y `SECRET_KEY` expuestas en el repo** → rotar YA y moverlas a variables de entorno **sin** defaults.
2. `DEBUG=True`, `ALLOWED_HOSTS=['*']`, `CORS_ALLOW_ALL_ORIGINS=True` en producción.
3. Contraseñas de usuarios en **texto plano**; login sin tokens; el resto de endpoints sin autenticación ni permisos.
4. `editar_producto` permite escribir **cualquier columna** de `productos` vía payload JSON.
5. Sin tests, sin serializers/validación de entrada, sin paginación, con bugs activos (`listar_productos` sin `buscar`).

Detalle completo y plan de mitigación: [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## Documentación del proyecto

- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — visión arquitectónica, deuda técnica y recomendaciones priorizadas
- [`docs/GLOSARIO.md`](docs/GLOSARIO.md) — glosario de dominio y formatos de datos
- [`docs/DIAGRAMAS.md`](docs/DIAGRAMAS.md) — diagramas ER, de despliegue y de secuencia (Mermaid)
- [`docs/ADRs/`](docs/ADRs/) — decisiones de arquitectura (ADR-001 … ADR-004)