# PLAN DE INTEGRACIÓN DE MÓDULOS

## Estado Actual
✅ Módulos activos (en raíz):
- roles/ → Roles_Principal.pyw (FUNCIONAL)
- empleados/ → SISTEMA_GESTION_EMPLEADOS_10.pyw (FUNCIONAL)
- reportes/ → reporte_nomina_*.pyw (FUNCIONAL)
- shared/ → obtener_datos.py (CRÍTICO)
- config/ → openssl_legacy.cnf
- docs/ → Documentación centralizada

## Módulos a Integrar

### 1. HISTORIAL PRESTAMOS ✅ PRIORIDAD ALTA
**Estado:** Listo para integrar  
**Esfuerzo:** BAJO (1-2 horas)

**Plan:**
```
1. Revisar HISTORIAL_PRESTAMOS_10.pyw
2. Agregar método en Sistema_INSEVIG.pyw: _abrir_prestamos()
3. Agregar pestaña "💰 Préstamos" en dashboard
4. Testear con SQL Server y Supabase
5. Mover a carpeta prestamos/ (opcional)
```

**Integración en Sistema_INSEVIG.pyw:**
```python
# En opciones del sidebar:
("💰 Préstamos", self._abrir_prestamos),

# Nuevo método:
def _abrir_prestamos(self):
    from "HISTORIAL PRESTAMOS".HISTORIAL_PRESTAMOS_10 import HistorialPrestamos
    ventana = tk.Toplevel(self.root)
    app = HistorialPrestamos(ventana)
```

---

### 2. TOTAL_OSERVACIONES ⏱️ PRIORIDAD MEDIA
**Estado:** En desarrollo, requiere análisis  
**Esfuerzo:** MEDIO (2-3 horas)

**Plan:**
```
1. Identificar archivo principal .pyw
2. Revisar funcionalidad y dependencias
3. Completar documentación
4. Testear conexión Supabase
5. Integrar después de Préstamos
```

---

### 3. envio_roles ❌ PRIORIDAD BAJA
**Estado:** Duplicidad con Roles_Principal  
**Esfuerzo:** ALTO (requiere refactor)

**Decisión:** 
- ❌ NO integrar como módulo separado
- ✅ O FUSIONAR: Agregar función "Enviar Roles" en Roles_Principal.pyw
- Revisar ENVIO_ROLES_7.1.py (versión más reciente)

---

### 4. registrdor_vizulizador_egresosingresos ❌ PRIORIDAD BAJA
**Estado:** Incompleto  
**Esfuerzo:** ALTO (requiere completar)

**Decisión:**
- ❌ EN ESPERA - Evaluar si es necesario
- Posible fusión con HISTORIAL PRESTAMOS

---

## Estructura Final Propuesta

```
NOMINA_ROLES_SISTEMA_INSEVIG/
├── Sistema_INSEVIG.pyw (Dashboard con todas las pestañas)
├── roles/
├── empleados/
├── prestamos/          ← NUEVA (integrar HISTORIAL PRESTAMOS)
├── reportes/
├── shared/
├── config/
├── docs/
├── TOTAL_OSERVACIONES/ (en espera)
├── envio_roles/        (decisión: fusionar o descartar)
└── registrdor_vizulizador_egresosingresos/ (en espera)
```

---

## Pestañas Finales en Sistema_INSEVIG.pyw

```
📋 Roles de Pago        → roles/Roles_Principal.pyw
👥 Gestión Empleados    → empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw
💰 Préstamos            → prestamos/HISTORIAL_PRESTAMOS_10.pyw [NUEVA]
📊 Reportes             → reportes/reporte_nomina_GUI.pyw
⚙️ Configuración        → Settings dialog
🚪 Salir                → Exit
```

---

## Timeline de Integración

**Fase 1 (HOY):** HISTORIAL PRESTAMOS (2 horas)
- Integrar como pestaña
- Testear funcionamiento
- Mover a carpeta prestamos/

**Fase 2 (MAÑANA):** TOTAL_OSERVACIONES (3 horas)
- Completar análisis
- Documentar
- Integrar si vale la pena

**Fase 3 (SEMANA):** envio_roles (TBD)
- Decidir: fusionar o descartar
- Si fusionar: refactor de Roles_Principal.pyw

---

## Checklist de Integración por Módulo

### HISTORIAL PRESTAMOS
- [ ] Revisar código HISTORIAL_PRESTAMOS_10.pyw
- [ ] Identificar dependencias
- [ ] Copiar a prestamos/
- [ ] Agregar import en Sistema_INSEVIG.pyw
- [ ] Agregar botón/pestaña
- [ ] Testear búsqueda SQL Server
- [ ] Testear búsqueda Supabase
- [ ] Commit: "Integrar módulo Préstamos"

### TOTAL_OSERVACIONES
- [ ] Identificar archivo .pyw principal
- [ ] Revisar funcionalidad
- [ ] Revisar dependencias
- [ ] Completar CLAUDE.md
- [ ] Testear
- [ ] Decidir integración

### envio_roles
- [ ] Revisar ENVIO_ROLES_7.1.py
- [ ] Comparar con Roles_Principal.pyw
- [ ] Decisión: fusionar vs descartar
- [ ] Si fusionar: refactor

---

## Notas Importantes

⚠️ **NO ROMPER:**
- `shared/obtener_datos.py` - Métodos críticos
- Métodos de búsqueda dual SQL/Supabase
- Mapeo de conceptos (CLASE → nombre)

✅ **MANTENER CONSISTENCIA:**
- Selector SQL Server/Supabase en cada módulo
- Dark mode con colores globales
- Logging/debugging centralizado
- Documentación CLAUDE.md en cada carpeta

🔐 **SEGURIDAD:**
- Nunca hardcodear credenciales
- Supabase es READ-ONLY por ahora
- SQL Server es fuente de verdad
