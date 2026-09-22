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
- `screenshot_desktop.png` — captura a página completa.

Ambas están excluidas del repositorio por `.gitignore`.

## Automatización con GitHub Actions

El workflow [`.github/workflows/auditoria.yml`](.github/workflows/auditoria.yml)
ejecuta la auditoría **de lunes a viernes a las 9:00 AM (Europe/Madrid)**.

- El `cron` de GitHub Actions está en UTC: `0 7 * * 1-5` (9:00 AM hora peninsular en
  verano; en invierno, al no ajustarse por horario de verano, se ejecuta a las 8:00 AM).
- El PDF y la captura se publican como **artifact** de la ejecución
  (`informe-auditoria-<número de run>`), disponibles 90 días.
- También puede lanzarse manualmente: pestaña **Actions → Auditoría web → Run workflow**.

```bash
gh workflow run auditoria.yml   # lanzada manual desde CLI
```
