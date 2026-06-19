# ⚡ CREAR TABLA EN SUPABASE (MANUAL)

## Credenciales encontradas ✓

```
URL: https://buzcapcwmksasrtjofae.supabase.co
KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1emNhcGN3bWtzYXNydGpvZmFlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTk5NjgzNywiZXhwIjoyMDY1NTcyODM3fQ.gD_Qz6i2WzFqofBclS8BERVN-mALCzhFFS83IsKi1Rg
```

## Tablas existentes en Supabase ✓

- ✓ rpemplea (Empleados)
- ✓ rpingdesres (Ingresos/Egresos)
- ✓ rpingdes (Movimientos)
- ✓ rphistor_temp (Histórico)
- ✓ dbtablas (Catálogos)

---

## Crear tabla historial_prestamos_sqlite

### 1. Ve a Supabase SQL Editor

👉 **https://app.supabase.com/project/buzcapcwmksasrtjofae/sql**

(Proyecto: buzcapcwmksasrtjofae)

### 2. Copia y ejecuta este SQL

```sql
-- Crear tabla
CREATE TABLE historial_prestamos_sqlite (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    empleado TEXT NOT NULL,
    fecha TEXT,
    ingreso NUMERIC DEFAULT 0,
    egreso NUMERIC DEFAULT 0,
    concepto TEXT,
    tipo TEXT,
    numero_fila INTEGER,
    observaciones TEXT,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear índices para performance
CREATE INDEX idx_empleado ON historial_prestamos_sqlite(empleado);
CREATE INDEX idx_fecha ON historial_prestamos_sqlite(fecha);

-- Habilitar Row Level Security
ALTER TABLE historial_prestamos_sqlite ENABLE ROW LEVEL SECURITY;

-- Permitir acceso público (ajusta según necesites)
CREATE POLICY "Acceso publico" ON historial_prestamos_sqlite
FOR ALL USING (true) WITH CHECK (true);
```

### 3. Presiona "Run" ▶️

Deberías ver: ✅ **Query executed successfully**

---

## Verificar tabla creada

En Supabase, ve a **Tablespara verificar:

```
✓ historial_prestamos_sqlite
  - id (BIGINT)
  - empleado (TEXT)
  - fecha (TEXT)
  - ingreso (NUMERIC)
  - egreso (NUMERIC)
  - concepto (TEXT)
  - tipo (TEXT)
  - numero_fila (INTEGER)
  - observaciones (TEXT)
  - creado_en (TIMESTAMP)
  - actualizado_en (TIMESTAMP)
```

---

## Próximos pasos

Una vez creada la tabla:

```bash
# 1. Migrar datos de SQLite a Supabase
python3 shared/migracion_prestamos_sqlite_supabase.py

# 2. Actualizar HISTORIAL_PRESTAMOS_10.pyw
# (Seguir guía en prestamos/MIGRACION_SUPABASE.md)

# 3. Testear módulo de Préstamos
python3 Sistema_INSEVIG.pyw
```

---

## Ayuda

- **Error "relation does not exist"**: La tabla no se creó. Intenta el SQL nuevamente.
- **Error "permission denied"**: Verifica que tienes permisos en Supabase.
- **Error "duplicate table"**: Tabla ya existe. Puedes continuar con la migración.

---

**⏱️ Tiempo estimado:** 2 minutos
