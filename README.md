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

## Uso

```bash
python auditor_web.py
```

Salidas (se regeneran en cada ejecución):

- `informe_auditoria_web.pdf` — informe ejecutivo.
- `screenshot_desktop.png` — captura a página completa.

## Ejecución programada

`ejecutar_auditoria.bat` lanza la auditoría y guarda la traza en `logs/`.
Está registrada en el Programador de tareas de Windows como **AuditRehametricsWeb**,
de lunes a viernes a las **9:00 AM**.

```bat
schtasks /query /tn "AuditRehametricsWeb"
schtasks /run  /tn "AuditRehametricsWeb"
```
