# AuditRehametricsWeb

Auditoría técnica automatizada de [https://rehametrics.com](https://rehametrics.com).

El script carga la página con Playwright (Chromium headless), acepta el banner de
cookies, fuerza el lazy-loading de imágenes/iframes/videos, comprueba el estado
HTTP de los enlaces, captura la página completa y genera un informe ejecutivo en PDF.

## Auditoría multi-página

Además de la principal, audita estas páginas:

- `/software/vr/`
- `/software/vr/rehabilitacion-cognitiva-en-realidad-virtual/`
- `/software/vr/fisioterapia/`
- `/software/vr/terapia-ocupacional/`
- `/software/cognitivo/`
- `/software/fisico/`
- `/validacion-clinica/`
- `/precios/`

La lista está en la constante `PAGINAS` de `auditor_web.py`. En cada página se
comprueba estado HTTP, tiempo de carga, errores de JS en consola y hasta 10 enlaces
(priorizando los enlaces propios de la página) con **caché compartida**: cada URL solo
se pide una vez a la red, pero se reporta en todas las páginas donde aparece.

El resultado es **un único PDF con una sección por página** (portada con resumen
global + una hoja por enlace con su tabla de métricas, captura y registros).

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

- `informe_auditoria_web.pdf` — informe único con una sección por página.
- `resumen.txt` — resumen en texto plano para Telegram.
- `capturas/<pagina>_completa.png` — captura de página completa, **2x** (para Telegram).
- `capturas/<pagina>_primera.png` — primera pantalla a **2x**.
- `capturas/<pagina>_pdf.jpg` — primera pantalla 1x en JPEG, la que se incrusta en el PDF.

Todo lo generado está excluido del repositorio por `.gitignore`.

## Automatización con GitHub Actions

El workflow [`.github/workflows/auditoria.yml`](.github/workflows/auditoria.yml)
ejecuta la auditoría **de lunes a viernes a las 9:00 AM (Europe/Madrid)**.

- El `cron` de GitHub Actions está en UTC: `0 7 * * 1-5` (9:00 AM hora peninsular en
  verano; en invierno, al no ajustarse por horario de verano, se ejecuta a las 8:00 AM).
- El PDF, el resumen y las capturas ligeras se publican como **artifact** de la
  ejecución (`informe-auditoria-<número de run>`), disponibles 90 días. Las capturas
  completas en PNG (~50 MB) solo van a Telegram: GitHub solo guarda 500 MB de artifacts.
- También puede lanzarse manualmente: pestaña **Actions → Auditoría web → Run workflow**
  (botón verde arriba a la derecha; no confundir con *Re-run all jobs*, que repite el
  commit de la ejecución original).

```bash
gh workflow run auditoria.yml   # lanzada manual desde CLI
```

## Notificaciones en Telegram

El workflow envía a Telegram el resumen de la auditoría (`resumen.txt`), el
`informe_auditoria_web.pdf` y las capturas de todas las páginas auditadas
(primera pantalla + página completa, en alta resolución 2x).

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
