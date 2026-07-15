# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Sistema_INSEVIG.pyw'],
    pathex=[],
    binaries=[],
    datas=[('shared', 'shared'), ('roles', 'roles'), ('empleados', 'empleados'), ('prestamos', 'prestamos'), ('reportes', 'reportes'), ('observaciones', 'observaciones'), ('registrdor_vizulizador_egresosingresos', 'registrdor_vizulizador_egresosingresos'), ('envio_roles', 'envio_roles'), ('cuadrardor_modificardor', 'cuadrardor_modificardor'), ('config', 'config')],
    hiddenimports=['pyodbc', 'pandas', 'reportlab', 'PIL', 'fitz', 'supabase'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='INSEVIG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='INSEVIG',
)
