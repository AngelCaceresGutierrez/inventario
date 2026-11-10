# ADR-003 — Autenticación por RUT + clave plana sin tokens ni hashing

- **Estado**: Aceptada (revisar URGENTEMENTE — hoy es el mayor riesgo del sistema)
- **Fecha de decisión**: previa a este registro; documentada el 2026-11-07

## Contexto

Sistema interno para pocos operadores confiables en puestos de venta, construido al mínimo costo y esfuerzo. No se usan `django.contrib.auth` ni sesiones DRF: los usuarios viven en la tabla `usuarios` de la BD externa con la clave guardada en texto plano.

## Decisión

`POST /api/iniciar_sesion/` recibe `usu_rut` y `usu_clave` y los compara directamente contra la tabla (`Usuarios.objects.get(usu_rut=..., usu_clave=...)`). **No se hashea la clave, no se emite token ni cookie de sesión**, y ningún otro endpoint verifica identidad: `crear_producto`, `editar_producto`, `crear_venta`, `traer_usuarios`, etc. quedan abiertos a cualquier origen (CORS abierto + `ALLOWED_HOSTS=['*']`).

## Consecuencias

**Positivas**

- Implementación mínima: un solo endpoint, sin infraestructura de sesiones/tokens.
- El frontend decide qué hacer tras el 200 (guarda `usuario_id` localmente).

**Negativas**

- **Claves legibles en la BD** (y en cualquier volcado/log que las incluya).
- **Todos los endpoints mutantes son públicos**: cualquier anónimo puede crear/editar productos y registrar ventas.
- Sin expiración, revocación ni intentos fallidos limitados (sin protección ante fuerza bruta).
- `traer_usuarios` expone los RUTs de todos los operadores sin auth.

**Mitigaciones sugeridas (P0)**: hashear con los hashers de Django (`make_password`/`check_password`) y migrar claves existentes; proteger los endpoints mutantes con al menos un token compartido por env var o con sesión/token DRF; eliminar o restringir `traer_usuarios`.