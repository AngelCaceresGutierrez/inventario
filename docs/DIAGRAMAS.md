# DIAGRAMAS — Proyecto "inventario"

Diagramas en sintaxis **Mermaid** (renderizables en GitHub, VS Code y mermaid.js). Registrados el 2026-11-07 a partir del código real.

## 1. Modelo de datos (ERD)

Entidades de `api_inventario/models.py` (todas `managed=False` sobre la BD Neon externa):

```mermaid
erDiagram
    DUENO {
        int due_id PK
        varchar due_nombre "nullable"
        bool due_estado "nullable"
    }
    TIPO {
        int tip_id PK
        varchar tip_nombre
    }
    UBICACION {
        int ubi_id PK
        varchar ubi_nombre
    }
    PRODUCTOS {
        int pro_id PK
        varchar pro_nombre "nullable"
        varchar pro_codigo "codigo de 8 digitos, unicidad en app"
        int pro_precio "nullable"
        int pro_cantidad "nullable"
        varchar pro_precio_oferta "formato NxM, nullable"
        int pro_estado "nullable"
        int pro_ubicacion FK
        int pro_dueno FK
        int pro_tipo FK
    }
    USUARIOS {
        int usu_id PK
        varchar usu_rut UK "unico"
        varchar usu_clave "texto plano, nullable"
        varchar usu_nombre "nullable"
        bool usu_estado "nullable"
    }
    VENTAS {
        int ven_id PK
        datetime ven_fecha_registro "nullable"
        varchar ven_productos "pares id_cantidad separados por punto y coma"
        int ven_monto_total "nullable"
        int ven_puesto "referencia logica a puestos, sin FK"
    }
    PUESTOS {
        int pue_id PK
        varchar pue_nombre
    }

    DUENO ||--o{ PRODUCTOS : "pro_dueno"
    TIPO ||--o{ PRODUCTOS : "pro_tipo"
    UBICACION ||--o{ PRODUCTOS : "pro_ubicacion"
```

**Relaciones reales (FK en BD)**: `Productos → Ubicacion`, `Productos → Dueno`, `Productos → Tipo`.

**Sin clave foránea**:

- `Ventas.ven_productos` referencia a productos vía el **string** `id_cantidad;...` (ADR-002).
- `Ventas.ven_puesto` es un entero que referencia **lógicamente** a `Puestos`, sin FK.
- `Usuarios` es totalmente independiente del resto del modelo.

## 2. Arquitectura / despliegue

```mermaid
flowchart LR
    subgraph cliente["Cliente"]
        SPA["SPA frontend externa<br/>(punto de venta)"]
    end
    subgraph render["Render — free tier"]
        SVC["Servicio web<br/>inventario-mzod.onrender.com"]
        subgraph proc["Proceso gunicorn"]
            DJ["Django 5.2 (WSGI)"]
            KA["GET /api/estoy_vivo/<br/>sleep 8 min"]
        end
    end
    subgraph neon["Neon Tech"]
        DB[("PostgreSQL neondb")]
    end
    SPA -->|"HTTP JSON /api/*"| SVC
    SVC --> DJ
    DJ -->|"psycopg2 sslmode=require"| DB
    KA -.->|"luego hace GET a sí mismo<br/>(bucle keep-alivo)"| SVC
```

El bucle `-.->` del keep-alive es **auto-sostenido**: la primera llamada externa dispara un ciclo infinito de peticiones cada ~8 minutos que mantiene despierto el servicio (ADR-004), a costa de bloquear un worker.

## 3. Secuencia — iniciar_sesion

```mermaid
sequenceDiagram
    actor U as Cliente (SPA)
    participant A as API Django (Render)
    participant DB as Neon PostgreSQL
    U->>A: POST /api/iniciar_sesion/ {usu_rut, usu_clave}
    A->>DB: SELECT * FROM usuarios WHERE usu_rut = ? AND usu_clave = ?
    DB-->>A: 1 fila (coincidencia) o 0 filas
    alt credenciales correctas
        A-->>U: 200 {"message": "Inicio de sesión exitoso", "usuario_id": n}
    else no existe coincidencia
        A-->>U: 400 {"message": "Credenciales incorrectas"}
    end
    Note over A,DB: La clave se compara en TEXTO PLANO (sin hash).<br/>No se emite ningún token: el resto de endpoints queda abierto.
```

## 4. Secuencia — crear_venta

```mermaid
sequenceDiagram
    actor U as Cliente (SPA)
    participant A as API Django
    participant DB as Neon PostgreSQL
    U->>A: POST /api/crear_venta/ {arr: [{pro_id, pro_cantidad, pro_subtotal, ..., puesto}]}
    loop por cada elemento de arr
        A->>A: monto_total += pro_subtotal (confía en el cliente)
        A->>A: ven_productos += "pro_id_pro_cantidad" + separador
    end
    Note over A: ven_puesto se lee del ÚLTIMO elemento del array<br/>(acoplamiento frágil)
    A->>DB: INSERT INTO ventas (ven_monto_total, ven_productos, ven_fecha_registro, ven_puesto)
    DB-->>A: OK
    A-->>U: 200 {"message": "Venta creada exitosamente"}
    Note over A,DB: No hay validación ni recálculo de precios al vender.<br/>Si el INSERT falla: 500 {"error": "..."}.
```

## 5. Secuencia — totales_vendidos_por_dia

```mermaid
sequenceDiagram
    actor U as Cliente (SPA)
    participant A as API Django
    participant DB as Neon PostgreSQL
    U->>A: GET /api/totales_vendidos_por_dia/?fecha=YYYY-MM-DD
    Note over A: Sin fecha → usa hoy (datetime.now del servidor, UTC)
    A->>DB: SELECT * FROM ventas WHERE date(ven_fecha_registro) = fecha
    DB-->>A: ventas del día
    loop por cada venta
        A->>A: total_vendido += ven_monto_total
        A->>A: split(";") → pares id_cantidad
        loop por cada par id_cantidad
            A->>DB: SELECT producto por pro_id (N+1)
            DB-->>A: pro_precio, pro_precio_oferta, pro_tipo_id, pro_dueno_id
            A->>A: recalcular monto con oferta "NxM"<br/>(grupos de oferta + restantes a precio normal)
            A->>A: acumular por dueño (1=Mireya, 2=Ivan, 3=Paulina)<br/>y por tipo (1=Ropa, 2=Paquetería, 3=Útiles)
        end
    end
    A-->>U: 200 {"respuesta": {fecha, total_vendido, vendido_mireya, vendido_ivan, vendido_paulina, vendido_ropa, vendido_paqueteria, vendido_utiles, productos[]}}
    Note over A: Puede divergir de ven_monto_total si precios u ofertas<br/>cambiaron después de la venta (ADR-002).
```

## 6. Mantener los diagramas

- Si cambia el esquema de la BD (fuera de Django), actualizar primero `models.py`, luego este documento y [`ARQUITECTURA.md`](ARQUITECTURA.md).
- Regla práctica: **todo cambio de contrato de un endpoint** (ruta, payload, respuesta) exige actualizar el diagrama de secuencia correspondiente y la tabla de endpoints del `README.md`.