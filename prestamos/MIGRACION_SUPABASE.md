# Migración: SQLite → Supabase para Préstamos

## ¿Por qué migrar?

Actualmente, el módulo de Préstamos usa:
- **SQL Server**: Para datos actuales (RPINGDES, RPHISTOR, RPEMPLEA)
- **SQLite local**: Para historial de préstamos (Saldo_prestamos_driver.db)

**Problema:** SQLite no funciona bien en Linux o sin montaje de red.

**Solución:** Migrar todo a **Supabase** para que funcione desde cualquier lugar.

---

## Paso 1: Crear tabla en Supabase

```sql
CREATE TABLE historial_prestamos_sqlite (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    empleado TEXT NOT NULL,
    fecha TEXT,
    ingreso NUMERIC,
    egreso NUMERIC,
    concepto TEXT,
    tipo TEXT,
    numero_fila INTEGER,
    observaciones TEXT,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_empleado ON historial_prestamos_sqlite(empleado);
CREATE INDEX idx_fecha ON historial_prestamos_sqlite(fecha);
```

---

## Paso 2: Ejecutar script de migración

```bash
# Asegúrate de tener credenciales Supabase
export SUPABASE_URL="https://tu-proyecto.supabase.co"
export SUPABASE_KEY="tu-clave-publica"

# O crea config/supabase.yaml con:
# url: https://tu-proyecto.supabase.co
# key: tu-clave-publica

# Ejecutar migración
python3 shared/migracion_prestamos_sqlite_supabase.py
```

**Output esperado:**
```
✓ Encontrado: \\server\Respaldo 2017\Base\Saldo_prestamos_driver.db
✓ Conectado a Supabase
✓ Tabla ya existe
📖 Leyendo datos de SQLite...
✓ 2847 registros encontrados
📤 Preparando datos para Supabase...
⬆️ Subiendo a Supabase...
  ✓ 100/2847 registros
  ✓ 200/2847 registros
  ...
✅ Migración completada: 2847/2847 registros
```

---

## Paso 3: Modificar HISTORIAL_PRESTAMOS_10.pyw

Cambiar:
```python
def obtener_historial_sqlite(self, codigo_empleado):
    conn = self.conectar_sqlite()
    cursor = conn.cursor()
    cursor.execute(...)
```

Por:
```python
def obtener_historial_supabase(self, codigo_empleado):
    from supabase import create_client
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    response = client.table('historial_prestamos_sqlite')\
        .select('*')\
        .eq('empleado', str(codigo_empleado))\
        .execute()
    return response.data
```

---

## Paso 4: Actualizar llamadas en HISTORIAL_PRESTAMOS_10.pyw

**Buscar:**
```python
movimientos_sqlite = self.obtener_historial_sqlite(codigo_empleado)
```

**Cambiar a:**
```python
movimientos_sqlite = self.obtener_historial_supabase(codigo_empleado)
```

---

## Ventajas después de migrar

✅ Funciona desde **cualquier lugar** (no necesita montaje de red)  
✅ **Compatible con Linux**  
✅ Sincronización automática con resto de Supabase  
✅ **Respaldos automáticos** en Supabase  
✅ **Acceso concurrente** sin problemas de bloqueos  
✅ **API REST** para integraciones futuras  

---

## Alternativa: Usar fallback automático

Si prefieres mantener SQLite como alternativa:

```python
def obtener_historial(self, codigo_empleado):
    try:
        # Intentar Supabase primero
        return self.obtener_historial_supabase(codigo_empleado)
    except:
        # Fallback a SQLite
        return self.obtener_historial_sqlite(codigo_empleado)
```

---

## Verificar migración

### En Supabase:
```sql
SELECT COUNT(*) as total FROM historial_prestamos_sqlite;
SELECT DISTINCT empleado FROM historial_prestamos_sqlite LIMIT 10;
```

### En el módulo de Préstamos:
- Abre módulo 💰 Préstamos
- Busca un empleado
- Verifica que muestre **historial completo** desde Supabase

---

## Problemas comunes

### "Connection refused" a SQLite
**Causa:** Montaje de red no disponible  
**Solución:** Usar script de migración e ir a Supabase

### "Table already exists"
**Causa:** Tabla ya migrada  
**Solución:** Limpiar tabla y ejecutar script de nuevo, o insertar registro por registro

### Registros no aparecen en módulo
**Causa:** HISTORIAL_PRESTAMOS_10.pyw aún usa SQLite  
**Solución:** Actualizar método `obtener_historial_sqlite()` → `obtener_historial_supabase()`

---

## Próximos pasos

1. ✅ Crear tabla en Supabase
2. ✅ Ejecutar script de migración
3. 📝 Modificar HISTORIAL_PRESTAMOS_10.pyw
4. 🧪 Testear módulo de Préstamos
5. 🚀 Usar desde cualquier lugar con Supabase
