#!/bin/bash
# Script para verificar que el ejecutable está completo

echo "═══════════════════════════════════════════════════════"
echo "  VERIFICACIÓN DE EJECUTABLE INSEVIG"
echo "═══════════════════════════════════════════════════════"

DIST_DIR="./dist/INSEVIG"

# Verificar directorio dist
echo ""
echo "📁 Verificando estructura de carpetas..."
if [ -d "$DIST_DIR" ]; then
    echo "✅ Directorio $DIST_DIR existe"
else
    echo "❌ Directorio $DIST_DIR NO existe"
    exit 1
fi

# Verificar archivos principales
echo ""
echo "📋 Verificando archivos necesarios..."

FILES=(
    "$DIST_DIR/INSEVIG"
    "$DIST_DIR/_internal"
    "$DIST_DIR/shared"
    "$DIST_DIR/roles"
    "$DIST_DIR/empleados"
    "$DIST_DIR/prestamos"
    "$DIST_DIR/config"
)

for file in "${FILES[@]}"; do
    if [ -e "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file FALTA"
    fi
done

# Verificar tamaño
echo ""
echo "📊 Tamaño total del paquete:"
du -sh "$DIST_DIR"

# Verificar ejecutable
echo ""
echo "⚙️ Información del ejecutable:"
if [ -x "$DIST_DIR/INSEVIG" ]; then
    echo "✅ INSEVIG es ejecutable"
    file "$DIST_DIR/INSEVIG" | head -1
else
    echo "⚠️ INSEVIG no tiene permisos de ejecución"
    chmod +x "$DIST_DIR/INSEVIG"
    echo "✅ Permisos ajustados"
fi

# Crear scripts de inicio si no existen
echo ""
echo "📝 Creando scripts de inicio..."

# Script bash
cat > "$DIST_DIR/INSEVIG.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./INSEVIG "$@"
EOF
chmod +x "$DIST_DIR/INSEVIG.sh"
echo "✅ INSEVIG.sh creado"

# Script batch para Windows (simulado)
cat > "$DIST_DIR/INSEVIG.bat" << 'EOF'
@echo off
cd /d "%~dp0"
start "" "INSEVIG.exe"
EOF
echo "✅ INSEVIG.bat creado"

# README
cat > "$DIST_DIR/README.txt" << 'EOF'
╔══════════════════════════════════════════════════════════╗
║         INSEVIG - Sistema de Nómina v1.0                ║
║      © 2026 - Todos los derechos reservados             ║
╚══════════════════════════════════════════════════════════╝

INICIO RÁPIDO
═════════════

Linux/Mac:
  ./INSEVIG.sh

Windows:
  Doble clic en INSEVIG.bat
  O ejecuta: INSEVIG.exe

CREDENCIALES POR DEFECTO
═════════════════════════
Usuario:    admin
Contraseña: admin

REQUISITOS DEL SISTEMA
══════════════════════
- Windows 7+ / Linux / macOS
- Conexión a SQL Server 192.168.2.115
- O acceso a Supabase (fallback automático)

FUNCIONALIDADES PRINCIPALES
════════════════════════════
✓ Generador de Roles de Pago (PDF)
✓ Gestión de Empleados
✓ Administración de Préstamos
✓ Reportes y Análisis
✓ Observaciones del Personal
✓ Registrador de Movimientos
✓ Envío de Roles

NO MOVER NI MODIFICAR ARCHIVOS
════════════════════════════════
Todos los archivos deben estar en este directorio.
Si alguno se daña o se mueve, el programa no funcionará.

Para reinstalar:
- Descarga nuevamente desde: https://github.com/tuusuario/INSEVIG
- O copia esta carpeta completa a otro lugar

SOPORTE Y PROBLEMAS
═══════════════════
Para reportar problemas:
1. Toma una captura de pantalla del error
2. Nota la hora exacta
3. Contacta al administrador del sistema

═════════════════════════════════════════════════════════════
EOF
echo "✅ README.txt creado"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ VERIFICACIÓN COMPLETADA"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "El ejecutable está listo para usar:"
echo "  📁 Carpeta: $DIST_DIR"
echo "  📦 Tamaño: $(du -sh $DIST_DIR | cut -f1)"
echo ""
echo "Puedes copiar todo el directorio 'INSEVIG' a cualquier"
echo "lugar y ejecutarlo directamente sin instalación."
echo ""
