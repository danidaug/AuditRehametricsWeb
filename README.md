# AuditRehametricsWeb

Auditoría técnica automatizada de [https://rehametrics.com](https://rehametrics.com).

El script carga la página con Playwright (Chromium headless), acepta el banner de
cookies, fuerza el lazy-loading de imágenes/iframes/videos, comprueba el estado
HTTP de los enlaces, captura la página completa y genera un informe ejecutivo en PDF.

## Requisitos

- Python 3.10+
- Dependencias:

```bash
pip install -r requirements.txt
playwright install chromium
```

## Uso local

```bash
python auditor_web.py
```

Salidas (se regeneran en cada ejecución):

- `informe_auditoria_web.pdf` — informe ejecutivo.
- `screenshot_desktop.png` — captura completa a página completa, **2x** (2880 px de ancho).
- `screenshot_inicio.png` — primera pantalla (viewport) a **2x**, la que mejor se ve en Telegram.
- `screenshot_informe.png` — copia 1x que se incrusta en el PDF, para no engordar el informe.
- `resumen.txt` — resumen en texto plano para Telegram.

Todas están excluidas del repositorio por `.gitignore`.

## Automatización con GitHub Actions

El workflow [`.github/workflows/auditoria.yml`](.github/workflows/auditoria.yml)
ejecuta la auditoría **de lunes a viernes a las 9:00 AM (Europe/Madrid)**.

- El `cron` de GitHub Actions está en UTC: `0 7 * * 1-5` (9:00 AM hora peninsular en
  verano; en invierno, al no ajustarse por horario de verano, se ejecuta a las 8:00 AM).
- El PDF, el resumen y las capturas se publican como **artifact** de la ejecución
  (`informe-auditoria-<número de run>`), disponibles 90 días.
- También puede lanzarse manualmente: pestaña **Actions → Auditoría web → Run workflow**
  (botón verde arriba a la derecha; no confundir con *Re-run all jobs*, que repite el
  commit de la ejecución original).

```bash
gh workflow run auditoria.yml   # lanzada manual desde CLI
```

## Notificaciones en Telegram

El workflow envía a Telegram el resumen de la auditoría (`resumen.txt`), el
`informe_auditoria_web.pdf`, la primera pantalla (`screenshot_inicio.png`) y la
captura completa (`screenshot_desktop.png`), ambas en alta resolución 2x.

**1. Crea el bot** — en Telegram, habla con [@BotFather](https://t.me/BotFather),
ejecuta `/newbot`, elige nombre y guarda el **token** que te da
(alfanumérico con dos `:`).

**2. Obtén tu chat_id** — envía un mensaje cualquiera a tu bot (p. ej. `hola`)
y abre en el navegador:

```
https://api.telegram.org/bot<TU_TOKEN>/getUpdates
```

Busca `"chat":{"id": 123456789 ...` → ese número es tu `TELEGRAM_CHAT_ID`.

**3. Guarda los Secrets** — en el repo: **Settings → Secrets and variables →
Actions → New repository secret** y añade:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | el token de BotFather |
| `TELEGRAM_CHAT_ID` | tu id de chat |

Mientras no existan, el paso *"Enviar resultado a Telegram"* se omite y la
ejecución sigue siendo válida (el informe se descarga como artifact).

**4. Prueba** — *Actions → Auditoría web → Run workflow*.
