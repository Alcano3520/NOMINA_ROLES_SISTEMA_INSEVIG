# Envío de roles por correo — especificación de la interfaz Tkinter

Fuente: `envio_roles/ENVIO_ROLES_7_NUEVO.pyw` (~801 líneas). Ventana única.
Web: `insevig_web/pages/envio/` + `core/email/`.

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta.

---

## Controles

| Caja / campo | Detalle | Web |
|---|---|---|
| **Base de Datos** | ruta al SQLite/BD de empleados | ✅ (usa `core/datos`) |
| **Excluir Departamentos por Palabras Clave** | entry de keywords | 🟡 |
| **Ordenamiento** | criterio de orden de la cola de envío | 🟡 |
| **Archivo Excel** | Excel con los destinatarios (cédula → email) | ✅ (`rx.upload` / parser) |
| **Carpeta PDFs** | dónde están los roles ya generados (empareja por cédula) | 🟡 → salida del Job de Roles o `rx.upload` |
| **Correo CC / CCO** | copias | 🟡 |
| **Intervalo (segundos)** | pausa entre envíos (default 5) | ✅ (`envio_lote` con intervalo) |
| **Iniciar Envío / Detener Envío** | | ✅ (Job reanudable + cancelación) |

## Motor (`core/email/`)
- Backend por config: **GraphSender** (Microsoft 365, permiso `Mail.Send`) o
  **SmtpSender** (`smtp.office365.com:587` STARTTLS). Sustituye a Outlook COM del `.pyw`.
- Plantilla HTML del correo → Jinja2.
- **Job reanudable e idempotente**: `EmailSendLog` evita doble envío si se corta.
- `encontrar_pdf_por_cédula`, sustitución de placeholders, semántica intervalo/stop.

## Lo que falta en la web
1. Campos **CC / CCO** y **exclusión de departamentos por keyword** y **orden de
   la cola** expuestos en la página `/envio`.
2. Emparejar los PDF: hoy hay que subirlos o tomar la salida del Job de Roles;
   confirmar el flujo end-to-end.
3. (infra) Registrar la app en Entra ID (Graph) **o** una cuenta SMTP con app
   password — no es código, es configuración del `.env` en el servidor.
