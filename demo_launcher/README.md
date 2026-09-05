# Lanzador de demo (INSEVIG_Demo.exe)

Doble clic abre la app web (Reflex) en el navegador. Se genera automáticamente
en GitHub Actions (`.github/workflows/build-demo-launcher-exe.yml`) — no hace
falta compilarlo a mano: cada push a `main` que toque `demo_launcher/` (o el
botón "Run workflow" en la pestaña Actions de GitHub) deja el .exe listo para
descargar como artifact de esa corrida.

## Qué hace
1. Revisa si la app ya está corriendo en la URL configurada (por defecto
   `http://localhost:3000`).
2. Si no, y encuentra el proyecto instalado junto al .exe (o en la ruta de
   `demo_config.ini`), lo levanta con el mismo comando que
   `scripts/dev.sh` (`reflex run --env prod --single-port --frontend-port 3000`).
3. Abre el navegador en esa URL.

## Configurar (opcional)
Crear `demo_config.ini` junto al .exe:

```ini
[demo]
url = http://192.168.2.50:3000
proyecto = C:\INSEVIG\web
```

Sin este archivo, asume `http://localhost:3000` y busca una carpeta
`insevig_web\` al lado del .exe.

## Requisito
Para que el paso 2 funcione, el proyecto (`insevig_web/`, `.venv/` con Reflex
instalado) debe estar ya clonado/instalado en esa PC. El .exe es solo un
lanzador — no empaqueta el backend Reflex completo (build de frontend, Node,
dependencias Python), que sigue instalándose una vez como indica
`CLAUDE.md` § "Objetivo de Arquitectura Final".
