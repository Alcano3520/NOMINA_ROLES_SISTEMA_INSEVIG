# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['ENVIO_ROLES_7.1.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon_envio.ico', '.'),
        ('crear_icono_envio.py', '.'),
    ],
    hiddenimports=[
        # pywin32 / win32com
        'win32com',
        'win32com.client',
        'win32com.server',
        'win32com.shell',
        'pythoncom',
        'pywintypes',
        'win32timezone',
        'win32api',
        'win32con',
        # pyodbc
        'pyodbc',
        # pandas / excel
        'pandas',
        'xlsxwriter',
        'openpyxl',
        # PIL
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        # tkinter
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        # stdlib usados
        're',
        'glob',
        'threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # librerías científicas/ML que no usa este programa
        'torch', 'torchvision', 'torchaudio',
        'scipy', 'sklearn', 'matplotlib', 'sympy',
        'tensorflow', 'keras', 'onnxruntime',
        'cv2', 'skimage',
        'IPython', 'jupyter', 'notebook',
        'bokeh', 'plotly', 'altair',
        'numba', 'cupy',
        'fsspec', 'aiohttp', 'grpc',
        'wx', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Envio_roles_v7',
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
    icon=['icon_envio.ico'],
)
