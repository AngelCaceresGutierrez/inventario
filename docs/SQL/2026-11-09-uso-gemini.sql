-- ============================================================
-- 2026-11-09 — Contador informativo del free tier de Gemini
-- Una fila por día (ug_fecha PK): lecturas y tokens consumidos
-- por leer_nota. Solo informativo: el límite (GEMINI_RPD_LIMITE)
-- NUNCA bloquea en el servidor; la app muestra lo que queda.
-- Esquema gestionado con SQL manual fuera de Django (ADR-001).
-- ============================================================

CREATE TABLE IF NOT EXISTS uso_gemini (
    ug_fecha    DATE    PRIMARY KEY,
    ug_lecturas INTEGER NOT NULL DEFAULT 0,
    ug_tokens   INTEGER NOT NULL DEFAULT 0
);

-- La PK por día cubre el upsert diario y la lectura del estado;
-- la tabla crece 1 fila/día, no necesita índices adicionales.
