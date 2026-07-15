#!/usr/bin/env python3
"""
Script para empaquetar INSEVIG como ejecutable con PyInstaller
Crea una carpeta standalone con todo lo necesario para ejecutar
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def instalar_dependencias():
    """Instala las dependencias necesarias"""
    print("📦 Instalando dependencias...")
    deps = [
        'pyodbc',
        'pandas',
        'reportlab',
        'pillow',
        'pymupdf',  # fitz
        'supabase==2.7.4',
        'pyinstaller>=6.0'
    ]

    for dep in deps:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', dep])
            print(f"  ✅ {dep}")
        except:
            print(f"  ⚠️ {dep} (puede que ya esté instalado)")

def crear_ejecutable():
    """Crea el ejecutable con PyInstaller"""
    print("\n🔨 Creando ejecutable...")

    proyecto_dir = Path(__file__).parent
    spec_file = proyecto_dir / 'INSEVIG.spec'

    # Crear spec file
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import sys
import os

a = Analysis(
    ['{proyecto_dir}/Sistema_INSEVIG.pyw'],
    pathex=['{proyecto_dir}'],
    binaries=[],
    datas=[
        ('{proyecto_dir}/shared', 'shared'),
        ('{proyecto_dir}/roles', 'roles'),
        ('{proyecto_dir}/empleados', 'empleados'),
        ('{proyecto_dir}/prestamos', 'prestamos'),
        ('{proyecto_dir}/reportes', 'reportes'),
        ('{proyecto_dir}/observaciones', 'observaciones'),
        ('{proyecto_dir}/registrdor_vizulizador_egresosingresos', 'registrdor_vizulizador_egresosingresos'),
        ('{proyecto_dir}/envio_roles', 'envio_roles'),
        ('{proyecto_dir}/cuadrardor_modificardor', 'cuadrardor_modificardor'),
        ('{proyecto_dir}/config', 'config'),
    ],
    hiddenimports=[
        'pyodbc',
        'pandas',
        'reportlab',
        'PIL',
        'fitz',
        'supabase',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='INSEVIG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''

    with open(spec_file, 'w') as f:
        f.write(spec_content)

    # Ejecutar PyInstaller
    subprocess.check_call([
        sys.executable, '-m', 'PyInstaller',
        '--onedir',
        '--windowed',
        '--name=INSEVIG',
        str(spec_file)
    ])

    print("✅ Ejecutable creado en: dist/INSEVIG/")

def crear_script_inicio():
    """Crea un script start.bat para Windows"""
    print("\n📝 Creando script de inicio...")

    proyecto_dir = Path(__file__).parent
    dist_dir = proyecto_dir / 'dist' / 'INSEVIG'

    # Script para Windows
    bat_content = """@echo off
cd /d "%~dp0"
start "" "INSEVIG.exe"
"""

    with open(dist_dir / 'INSEVIG.bat', 'w') as f:
        f.write(bat_content)

    # Script para Linux/Mac
    sh_content = """#!/bin/bash
cd "$(dirname "$0")"
./INSEVIG &
"""

    sh_file = dist_dir / 'INSEVIG.sh'
    with open(sh_file, 'w') as f:
        f.write(sh_content)
    os.chmod(sh_file, 0o755)

    print("✅ Scripts de inicio creados")

def crear_readme():
    """Crea README en la carpeta dist"""
    print("\n📖 Creando README...")

    proyecto_dir = Path(__file__).parent
    dist_dir = proyecto_dir / 'dist' / 'INSEVIG'

    readme_content = """# INSEVIG - Sistema de Nómina

## Inicio rápido

### Windows
- Haz doble clic en `INSEVIG.bat`
- O ejecuta directamente `INSEVIG.exe`

### Linux / Mac
- Ejecuta: `./INSEVIG.sh`
- O: `./INSEVIG`

## Credenciales por defecto
- **Usuario**: admin
- **Contraseña**: admin

## Requisitos del sistema
- Windows 7+ / Linux / macOS
- Conexión a SQL Server (192.168.2.115) o Supabase
- Driver ODBC 17 for SQL Server (Windows automático, Linux instala: `sudo apt install odbc-mssql`)

## Funcionalidades
- 📋 Generador de Roles de Pago (PDF)
- 👥 Gestión de Empleados
- 💰 Administración de Préstamos
- 📊 Reportes y Análisis
- 📝 Observaciones
- 📥 Registrador de Egresos/Ingresos

## Solución de problemas

### Error de conexión SQL Server
Si ves "SSL Provider: unsupported protocol", el programa automáticamente fallback a Supabase.

### Archivo no encontrado
Asegúrate de que todos los archivos en `INSEVIG/` están presentes.
No muevas los archivos a otros directorios.

## Soporte
Para problemas, contacta al administrador del sistema.
"""

    with open(dist_dir / 'README.txt', 'w') as f:
        f.write(readme_content)

    print("✅ README creado")

def main():
    print("=" * 60)
    print("  EMPAQUETADOR INSEVIG v1.0")
    print("=" * 60)

    try:
        instalar_dependencias()
        crear_ejecutable()
        crear_script_inicio()
        crear_readme()

        print("\n" + "=" * 60)
        print("✅ ¡EMPAQUETADO COMPLETADO!")
        print("=" * 60)
        print("\n📁 La aplicación está en: dist/INSEVIG/")
        print("   Ejecutables:")
        print("   - Windows: INSEVIG.bat o INSEVIG.exe")
        print("   - Linux/Mac: INSEVIG.sh o INSEVIG")
        print("\n📦 Todo lo necesario está incluido en esa carpeta")
        print("   (puedes copiarla a cualquier lugar)")
        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\n❌ Error durante el empaquetado:")
        print(f"   {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
