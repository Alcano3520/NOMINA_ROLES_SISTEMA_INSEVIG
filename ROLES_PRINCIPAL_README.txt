════════════════════════════════════════════════════════════════════════════
ROLES_PRINCIPAL.PYW - SISTEMA INTEGRADO DE ROLES DE PAGO
════════════════════════════════════════════════════════════════════════════

DESCRIPCIÓN
-----------
Aplicación única que combina dos funcionalidades en un solo ejecutable con
pestañas (Notebook):

  Pestaña 1: VISUALIZADOR
    - Búsqueda rápida de un empleado por cédula o nombre
    - Generación on-demand de su rol de pago
    - Vista previa PDF en la ventana
    - Descarga rápida a carpeta

  Pestaña 2: GENERADOR
    - Generación batch de roles para múltiples empleados
    - Filtrado por período, nombre, cargo, depto
    - Filtrado por cédulas específicas (copiar/pegar)
    - Múltiples formatos de nombre de archivo
    - Opción de 2 roles por hoja para ahorro de papel
    - Logo automático en blanco y negro
    - Barra de progreso en tiempo real

REQUISITOS
----------
Python 3.7+
Librerías:
  - pyodbc (conexión SQL Server)
  - pandas (procesamiento de datos)
  - tkinter (interfaz gráfica - incluido en Python)
  - reportlab (generación PDF)
  - pillow (procesamiento de imágenes)
  - pymupdf/fitz (visualización PDF en ventana)

Instalar: pip install pyodbc pandas reportlab pillow pymupdf

CONEXIÓN A BASE DE DATOS
------------------------
Servidor: 192.168.2.115 (SQL Server 2008 R2)
Base de datos: insevig
Usuario: sa
Contraseña: puntosoft123*
Filtro: CODEMP='10' AND CODSUC='10' (INSEVIG)

Tablas consultadas (read-only):
  - RPEMPLEA: datos maestros de empleados
  - RPINGDES: movimientos del período abierto
  - RPHISTOR: movimientos de períodos cerrados
  - DBTABLAS: códigos descriptivos (cargo, depto, sección)

USO
---

VISUALIZADOR (Pestaña 1):
  1. Ingrese el período (YYYY-MM), ej: 2024-12
  2. Escriba nombre o cédula del empleado
  3. Presione Enter o haga clic en "🔍 Buscar"
  4. Se mostrará el rol en PDF en la pantalla
  5. Use "💾 Descargar PDF" para guardar en carpeta

GENERADOR (Pestaña 2):
  1. Seleccione período (YYYY-MM)
  2. (Opcional) Escriba filtro de texto (FENIX, CONTABLE, etc.)
  3. (Opcional) Pegue cédulas específicas (una por línea)
  4. Seleccione formato de nombre del archivo
  5. Marque opciones: "2 roles por hoja" o "Incluir logo"
  6. Seleccione carpeta padre donde crear subcarpeta YYYY-MM
  7. Haga clic en "🚀 Generar Roles"
  8. Espere a que complete (barra de progreso)
  9. Los PDFs se crean en: /carpeta/YYYY-MM/

ARCHIVOS GENERADOS
-------------------
Patrón de nombres (configurable en "Formato del nombre"):
  - cedula-nombre (predeterminado)
  - nombre-cedula
  - cedula-nombre-cargo
  - cedula-nombre-depto
  - nombre-cargo-cedula
  - depto-nombre-cedula

Ejemplo: 920116811_CRUZ_RAMON_202412.pdf

NOTAS IMPORTANTES
-----------------
✓ El archivo NO contiene credenciales en el código
✓ Las conexiones a BD son read-only (ApplicationIntent=ReadOnly)
✓ Los PDFs se generan en memoria (tempfile) antes de guardar
✓ La búsqueda rápida en Visualizador no carga todo el período
✓ El Generador batch usa datos consolidados para mejor rendimiento
✓ Los movimientos se buscan primero en RPINGDES, fallback a RPHISTOR
✓ Las cédulas en BD pueden ser float (920116811.0) - se convierten a string

COMPILACIÓN A EXE
-----------------
$ pyinstaller --onefile --windowed \
  --add-data="icon.ico:." \
  --name="Roles_Principal" \
  Roles_Principal.pyw

Los archivos se generarán en dist/Roles_Principal.exe

SOLUCIÓN DE PROBLEMAS
---------------------
Error: "No se pudo conectar a SQL Server"
  - Verificar que 192.168.2.115 es accesible
  - Verificar credenciales (sa/puntosoft123*)
  - Verificar que el puerto 1433 está abierto
  - En Linux, instalar: apt-get install unixodbc odbc-postgresql

Error: "ODBC Driver not found"
  - Instalar ODBC Driver 17: apt-get install msodbcsql17
  - O usar ODBC Driver 13, 11, SQL Server en Windows

Error: "No se encontraron datos para el período"
  - Verificar que el período existe en RPINGDES o RPHISTOR
  - Sistemas de nómina cerrados: los datos están en RPHISTOR

Error: "PDF no se muestra en ventana"
  - Instalar pymupdf: pip install pymupdf
  - El PDF se abrirá en el visor del sistema como fallback

════════════════════════════════════════════════════════════════════════════
