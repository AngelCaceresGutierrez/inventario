# ADR-004 — Keep-alive con request periódica para evitar el sleep de Render free tier

- **Estado**: Aceptada (candidata a reemplazo por cron externo)
- **Fecha de decisión**: previa a este registro; documentada el 2026-11-07

## Contexto

El servicio vive en el **free tier de Render**, que duerme la instancia tras ~15 minutos sin tráfico. El cold start posterior (1 minuto o más) es inaceptable para la operación de venta en los puestos. No se quiso pagar un plan superior ni configurar un servicio externo de pings.

## Decisión

El endpoint `GET /api/estoy_vivo/` implementa un **bucle auto-sostenido in-request**: al recibir una llamada, consulta productos de tipo 1 (devuelve una respuesta trivial) y ejecuta `estoy_vivo_func()`, que **duerme 8 minutos** dentro del worker y luego hace `requests.get` a `https://inventario-mzod.onrender.com/api/estoy_vivo/` (URL hardcodeada). Esa segunda llamada reinicia el ciclo: mientras el proceso viva, el servicio se auto-pinguea cada ~8 minutos y Render nunca lo duerme.

## Consecuencias

**Positivas**

- Costo cero y sin dependencias externas: el propio servicio se mantiene despierto.
- Simple de entender: un solo endpoint y una función.

**Negativas**

- **Bloquea un worker de gunicorn ~8 minutos por ciclo, indefinidamente**: con workers síncronos, la capacidad real de atender requests queda reducida de forma permanente.
- La cadena se corta si el proceso se reinicia (deploy, crash, restart de Render): alguien debe volver a llamar al endpoint para reactivarla.
- La URL está hardcodeada en `views.py` (no se puede probar el bucle contra otro entorno).
- `time.sleep` en un request HTTP es un anti-patrón: consumiría timeout en la mayoría de proxies/plataformas; solo sobrevive porque Render tolera respuestas lentas.

**Mitigaciones sugeridas (P2)**: reemplazar por un cron externo que haga GET cada 10 minutos (Render Cron Job, cron-job.org o UptimeRobot), eliminando el sleep in-request; al menos, mover el bucle a un hilo demonio con la URL leída de una variable de entorno.