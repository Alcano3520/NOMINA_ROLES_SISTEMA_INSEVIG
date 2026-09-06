# Lanzador de demo (INSEVIG_Demo.exe)

Doble clic abre la app web (Reflex) en el navegador. Se genera automáticamente
en GitHub Actions (`.github/workflows/build-demo-launcher-exe.yml`) — no hace
falta compilarlo a mano.

## Dos ubicaciones en el servidor NAS (192.168.2.181)

| Qué | Share oculto (UNC) | En el servidor | Unidad | Acceso |
|---|---|---|---|---|
| Código / proyecto Reflex | `\\192.168.2.181\Sistemas_Dev$` | `E:\Sistemas_Dev\` | `X:` | GRP_DEVS (control total). RRHH/general no lo ven |
| Lanzador `.exe` | `\\192.168.2.181\Apps_Empresa$\Lanzadores\` | `E:\Apps_Empresa\Lanzadores\` | `Y:` | GRP_DEVS control total; GRP_RRHH / GRP_GENERAL solo lectura/ejecución |

Ambos shares terminan en `$` (ocultos): no aparecen navegando "Red", hay que
escribir la ruta completa. Es grupo de trabajo, no dominio — cada PC de
desarrollo necesita una cuenta Windows en el servidor que sea miembro de
GRP_DEVS para llegar a `Sistemas_Dev$`.

`conectar_unidades.bat` mapea `X:` e `Y:`. El personal de RRHH/general **no**
lo necesita: ejecuta directamente
`\\192.168.2.181\Apps_Empresa$\Lanzadores\INSEVIG_Demo.exe`.

## Qué hace el .exe

1. Consulta si la app responde en la URL configurada (por defecto
   `http://192.168.2.181:3000`, el servicio Reflex del NAS).
2. Si responde → abre el navegador ahí. **Este es el caso normal para RRHH.**
3. Si no responde y llega al proyecto de desarrollo (`X:` o
   `\\192.168.2.181\Sistemas_Dev$`, solo GRP_DEVS), lo levanta con
   `reflex run --env prod --single-port --frontend-port 3000` y luego abre el
   navegador.
4. Si no responde ni llega al proyecto → abre la URL igual con un aviso.

El `.exe` es solo un lanzador: **no** empaqueta el backend Reflex (frontend
compilado, Node, dependencias Python). Eso se instala una vez en el NAS como
servicio Windows (ver `CLAUDE.md` § "Objetivo de Arquitectura Final").

## Configurar (opcional)

Copiar `demo_config.ini.ejemplo` como `demo_config.ini` junto al `.exe` solo
si hay que cambiar la URL o la ruta del proyecto. Rutas siempre UNC o unidad
mapeada (`X:`, `Y:`), nunca `C:\...`.

## Desplegar una versión nueva

GitHub Actions no llega a la LAN privada. Tras cada build (release `demo`):
descargar `INSEVIG_Demo.exe` y copiarlo a
`\\192.168.2.181\Apps_Empresa$\Lanzadores\` (o `Y:\Lanzadores\`) — lo hace
una cuenta GRP_DEVS. Si el `.exe` está en uso, copiar como
`INSEVIG_Demo_NUEVO.exe` y renombrar desde el Explorador.
