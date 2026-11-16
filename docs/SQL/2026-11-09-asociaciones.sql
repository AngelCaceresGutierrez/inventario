-- ============================================================
-- 2026-11-09 — Asociación automática de ventas libres a productos
-- Cada ítem de texto libre aprende su producto:
--   asociaciones_producto → texto normalizado → producto (permanente,
--     automatica=True si nació del match ≥ 0.9, False si fue manual).
--   pendientes_producto → textos sin match, con contador de veces que
--     aparecen; se borra la fila cuando se asocia manualmente.
-- Esquema gestionado con SQL manual fuera de Django (ADR-001).
-- ============================================================

CREATE TABLE IF NOT EXISTS asociaciones_producto (
    ap_id SERIAL PRIMARY KEY,
    ap_texto VARCHAR(100) NOT NULL UNIQUE,
    ap_producto_id INT NOT NULL,
    ap_automatica BOOLEAN NOT NULL DEFAULT FALSE,
    ap_fecha TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pendientes_producto (
    pp_id SERIAL PRIMARY KEY,
    pp_texto VARCHAR(100) NOT NULL UNIQUE,
    pp_veces INT NOT NULL DEFAULT 1,
    pp_fecha_ultimo TIMESTAMP NOT NULL DEFAULT now()
);

-- Las UNIQUE sobre el texto cubren el upsert/aprendizaje y la lectura
-- por texto; tablas pequeñas (1 fila por texto distinto), sin más índices.
