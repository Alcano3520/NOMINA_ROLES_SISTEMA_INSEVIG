-- ============================================================
-- CREAR TABLA: historial_prestamos_sqlite en Supabase
-- ============================================================
-- Copiar TODO este contenido y ejecutar en:
-- https://app.supabase.com/project/buzcapcwmksasrtjofae/sql/new
-- ============================================================

-- Eliminar tabla si existe (para limpiar)
DROP TABLE IF EXISTS historial_prestamos_sqlite CASCADE;

-- Crear tabla principal
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

-- Crear política de acceso público
CREATE POLICY "Acceso publico" ON historial_prestamos_sqlite
FOR ALL USING (true) WITH CHECK (true);

-- Verificar estructura (opcional)
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'historial_prestamos_sqlite';
