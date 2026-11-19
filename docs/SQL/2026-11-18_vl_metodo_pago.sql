-- ============================================================
-- 2026-11-18 — Método de pago por venta libre
-- Valores: efectivo, tarjeta, transferencia.
-- El DEFAULT rellena el histórico como efectivo y permite que el
-- backend anterior siga insertando sin el campo durante el despliegue.
-- ORDEN: aplicar ANTES de desplegar el backend que declara
-- vl_metodo_pago en el modelo VentasLibres.
-- Idempotente y transaccional: se puede ejecutar más de una vez.
-- Esquema gestionado con SQL manual fuera de Django (ADR-001).
-- ============================================================

BEGIN;

-- Si hay una transaccion abierta sobre la tabla, aborta en vez de encolar las
-- ventas detras del ALTER. Basta con reintentar: el script es idempotente.
SET LOCAL lock_timeout = '2s';

ALTER TABLE ventas_libres
    ADD COLUMN IF NOT EXISTS vl_metodo_pago VARCHAR(20) NOT NULL DEFAULT 'efectivo';

-- ADD CONSTRAINT no admite IF NOT EXISTS: se consulta el catálogo.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_ventas_libres_metodo_pago'
          AND conrelid = 'ventas_libres'::regclass
    ) THEN
        ALTER TABLE ventas_libres
            ADD CONSTRAINT chk_ventas_libres_metodo_pago
            CHECK (vl_metodo_pago IN ('efectivo', 'tarjeta', 'transferencia'));
    END IF;
END
$$;

COMMIT;

-- ============================================================
-- ROLLBACK (manual). Antes, retirar el backend que usa la columna:
-- borrarla elimina de forma definitiva los métodos de pago guardados.
-- ============================================================
-- BEGIN;
-- ALTER TABLE ventas_libres DROP CONSTRAINT IF EXISTS chk_ventas_libres_metodo_pago;
-- ALTER TABLE ventas_libres DROP COLUMN IF EXISTS vl_metodo_pago;
-- COMMIT;
