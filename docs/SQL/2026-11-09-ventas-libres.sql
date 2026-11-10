-- ============================================================
-- 2026-11-09 — Ventas libres + Lectura de nota por foto con IA
-- Fuente: docs/ARQUITECTURA-VENTAS-LIBRES.md §1.2 con la
-- MODIFICACIÓN del usuario (misma fecha): el diccionario de
-- correcciones es GLOBAL compartido entre puestos → sin cl_puesto,
-- UNIQUE solo sobre (cl_texto_crudo).
-- Esquema gestionado con SQL manual fuera de Django (ADR-001).
-- ============================================================

-- ============================================================
-- F1: Ventas libres (ítems sin vínculo a productos, por puesto)
-- ============================================================
CREATE TABLE IF NOT EXISTS ventas_libres (
    vl_id              SERIAL PRIMARY KEY,
    vl_nombre          VARCHAR(100) NOT NULL,
    vl_valor           INTEGER      NOT NULL CHECK (vl_valor >= 0),
    vl_fecha_registro  TIMESTAMP    NOT NULL DEFAULT now(),
    vl_puesto          INTEGER      NOT NULL
);

-- El reporte diario filtra por fecha: índice obligatorio.
CREATE INDEX IF NOT EXISTS idx_ventas_libres_fecha ON ventas_libres (vl_fecha_registro);

-- ============================================================
-- F2: Diccionario de correcciones de lectura — GLOBAL (sin puesto)
-- ============================================================
CREATE TABLE IF NOT EXISTS correcciones_lectura (
    cl_id                SERIAL PRIMARY KEY,
    cl_texto_crudo       VARCHAR(100) NOT NULL,  -- lo que leyó el modelo
    cl_nombre_corregida  VARCHAR(100) NOT NULL,  -- nombre real confirmado por el usuario
    cl_valor_corregido   INTEGER      NOT NULL CHECK (cl_valor_corregido >= 0),
    cl_fecha_registro    TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT uq_correcciones_texto UNIQUE (cl_texto_crudo)
);

-- El índice UNIQUE (cl_texto_crudo) cubre el upsert idempotente.
-- No se agrega otro índice.
