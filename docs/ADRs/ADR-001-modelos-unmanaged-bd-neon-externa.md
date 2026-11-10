# ADR-001 — Modelos Django unmanaged contra base de datos Neon externa

- **Estado**: Aceptada
- **Fecha de decisión**: previa a este registro (implícita en el código); documentada el 2026-11-07

## Contexto

La base de datos PostgreSQL en Neon Tech fue creada y gestionada **manualmente, fuera de Django**, antes de construir esta API (los modelos muestran la marca típica de `inspectdb`). Django llegó después como capa de acceso HTTP a ese esquema ya existente con datos reales.

## Decisión

Los 7 modelos (`Dueno`, `Productos`, `Tipo`, `Ubicacion`, `Usuarios`, `Ventas`, `Puestos`) se declaran con `managed = False` y `db_table` apuntando a las tablas existentes. Django **no crea, migra ni borra** ninguna tabla: el esquema se administra con SQL directo fuera del proyecto.

## Consecuencias

**Positivas**

- Respeta el esquema preexistente y sus datos sin riesgo de migraciones destructivas.
- Despliegue simple: `migrate` no es necesario para arrancar.
- El modelo Django sirve de documentación fiel del esquema real.

**Negativas**

- El esquema vive **fuera del repositorio**: no hay historial de cambios (migraciones) versionado.
- Cambios de esquema requieren SQL manual coordinado con la edición manual de `models.py`.
- Los tests no pueden usar una BD de prueba generada por Django (no hay fixtures de esquema).
- El admin de Django queda inútil en la práctica (`admin.py` está vacío).

**Mitigaciones futuras sugeridas**: versionar el SQL del esquema en el repo, o migrar progresivamente a modelos `managed` adoptando el esquema con migraciones iniciales (`migrate --fake-initial`).