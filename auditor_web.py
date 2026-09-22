import asyncio
import os
import time
from datetime import datetime
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

URL_TARGET = "https://rehametrics.com"

# Paginas adicionales a auditar, ademas de la principal
PAGINAS = [
    ("Software VR", "https://rehametrics.com/software/vr/"),
    ("Rehabilitacion cognitiva en RV", "https://rehametrics.com/software/vr/rehabilitacion-cognitiva-en-realidad-virtual/"),
    ("Fisioterapia", "https://rehametrics.com/software/vr/fisioterapia/"),
    ("Terapia ocupacional", "https://rehametrics.com/software/vr/terapia-ocupacional/"),
    ("Software cognitivo", "https://rehametrics.com/software/cognitivo/"),
    ("Software fisico", "https://rehametrics.com/software/fisico/"),
    ("Validacion clinica", "https://rehametrics.com/validacion-clinica/"),
    ("Precios", "https://rehametrics.com/precios/"),
]

CARPETA_CAPTURAS = "capturas"
ENLACES_POR_PAGINA = 10


def slug(url):
    """Identificador corto de una URL para nombrar los ficheros de captura."""
    path = urlparse(url).path.strip("/")
    return path.replace("/", "-") if path else "inicio"


def es_error_util(texto):
    """Filtra avisos triviales para no contaminar el informe."""
    return "Content Security Policy" not in texto and "requestStorageAccess" not in texto


def es_roto(estado):
    return not isinstance(estado, int) or estado >= 400 or estado == 0


async def preparar_pagina_y_multimedia(page):
    print("PROCESO: Gestionando cookies, videos, iFrames y recursos visuales...")

    # 1. Aceptar banner de cookies
    try:
        cookie_btn = page.locator("button:has-text('Aceptar'), button:has-text('Accept'), #cookie-accept, .cmplz-accept, .elementor-button")
        if await cookie_btn.count() > 0:
            await cookie_btn.first.click(timeout=2000)
            await asyncio.sleep(1)
    except Exception:
        pass

    # 2. Scroll progresivo para disparar Lazy Loading y IntersectionObservers
    height = await page.evaluate("document.body.scrollHeight")
    current_scroll = 0
    step = 250

    while current_scroll < height:
        current_scroll += step
        await page.evaluate(f"window.scrollTo(0, {current_scroll})")
        await asyncio.sleep(0.12)

    # 3. Forzar fuentes de imágenes, background-images y media
    await page.evaluate("""() => {
        document.querySelectorAll('img').forEach(img => {
            img.removeAttribute('loading');
            if (img.dataset.src) img.src = img.dataset.src;
            if (img.dataset.srcset) img.srcset = img.dataset.srcset;
            if (img.dataset.lazySrc) img.src = img.dataset.lazySrc;
        });

        document.querySelectorAll('*').forEach(el => {
            const dataBg = el.getAttribute('data-bg') || el.dataset.background || el.getAttribute('data-src');
            if (dataBg && !el.style.backgroundImage) {
                el.style.backgroundImage = `url("${dataBg}")`;
                el.style.backgroundSize = 'cover';
                el.style.backgroundPosition = 'center';
            }
            if (el.classList.contains('e-bg-lazyload')) {
                el.classList.remove('e-bg-lazyload');
            }
        });

        document.querySelectorAll('iframe').forEach(iframe => {
            let src = iframe.src || iframe.dataset.src;
            if (src) iframe.src = src;
            iframe.style.opacity = '1';
            iframe.style.visibility = 'visible';
        });

        document.querySelectorAll('video').forEach(video => {
            video.play().catch(() => {});
        });
    }""")

    # 4. Volver al inicio y dar tiempo de refresco a la red
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(3)
    print("ESTADO: Renderizado multimedia completado.")


async def probar_enlace(context, url):
    """Devuelve el codigo HTTP de un enlace, o una cadena si no responde."""
    try:
        test_page = await context.new_page()
        res = await test_page.goto(url, wait_until="domcontentloaded", timeout=10000)
        code = res.status if res else 0
        await test_page.close()
        return code
    except Exception:
        return "Timeout / No responde"


async def auditar_pagina(context, nombre, url, cache_enlaces):
    """Carga una pagina, deja sus capturas y devuelve todas sus metricas."""
    errores = []
    page = await context.new_page()
    page.on("console", lambda msg: errores.append(msg.text)
            if msg.type == "error" and es_error_util(msg.text) else None)

    print(f"AUDITORIA: [{nombre}] {url}")
    status = "N/A"
    inicio_carga = time.monotonic()
    try:
        res = await page.goto(url, wait_until="networkidle", timeout=30000)
        status = res.status if res else "N/A"
    except Exception as e:
        # 'networkidle' es estricto: si el sitio mantiene conexiones abiertas agotamos
        # el tiempo. Reintentamos con un criterio mas laxo para no abortar.
        print(f"AVISO: Espera de red inactiva agotada ({type(e).__name__}). Reintentando con 'load'...")
        try:
            res = await page.goto(url, wait_until="load", timeout=60000)
            status = res.status if res else "N/A"
        except Exception as e2:
            print(f"ERROR: No se pudo cargar {url}. Detalle: {e2}")
            await page.close()
            return {
                "nombre": nombre, "url": url, "status": "Timeout / No responde",
                "carga_s": 0.0, "captura_completa": None, "captura_primera": None,
                "captura_pdf": None, "probados": [], "rotos": [], "errores": [str(e2)],
            }
    carga_s = time.monotonic() - inicio_carga

    await preparar_pagina_y_multimedia(page)

    base = os.path.join(CARPETA_CAPTURAS, slug(url))
    captura_completa = base + "_completa.png"   # 2x, para Telegram
    captura_primera = base + "_primera.png"     # 2x, primera pantalla
    captura_pdf = base + "_pdf.jpg"             # 1x JPEG, para el PDF

    print(f"CAPTURA: Generando capturas de [{nombre}]...")
    await page.screenshot(path=captura_completa, full_page=True, scale="device")
    await page.screenshot(path=captura_primera, full_page=False, scale="device")
    await page.screenshot(path=captura_pdf, full_page=False, scale="css",
                          type="jpeg", quality=85)

    hrefs = await page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
    links_unicos = list(dict.fromkeys(h for h in hrefs if h and h.startswith("http")))

    # Prioriza los enlaces propios de esta pagina sobre los comunes de la navegacion:
    # si no, todas las secciones analizarian los mismos 10 enlaces del menu.
    prefijo = urlparse(url).path
    links_unicos.sort(key=lambda h: 0
                      if urlparse(h).path.startswith(prefijo) and urlparse(h).path != prefijo
                      else 1)
    links = links_unicos[:ENLACES_POR_PAGINA]

    print(f"ANALISIS: [{nombre}] comprobando {len(links)} enlaces...")
    probados = []
    rotos = []
    for link in links:
        # Cache compartido: cada enlace solo se pide una vez, pero se reporta en
        # todas las paginas donde aparece.
        if link not in cache_enlaces:
            cache_enlaces[link] = await probar_enlace(context, link)
        estado = {"url": link, "status": cache_enlaces[link]}
        probados.append(estado)
        if es_roto(estado["status"]):
            rotos.append(estado)

    await page.close()
    return {
        "nombre": nombre, "url": url, "status": status, "carga_s": carga_s,
        "captura_completa": captura_completa, "captura_primera": captura_primera,
        "captura_pdf": captura_pdf, "probados": probados, "rotos": rotos,
        "errores": errores,
    }


async def auditar_web():
    print(f"INICIO: Iniciando auditoria tecnica de {URL_TARGET} y sus paginas asociadas...")
    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)

    paginas = []
    cache_enlaces = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-components-update",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )

        # User-Agent real y Referer para evitar el bloqueo HTTP 403 en CDNs
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={
                "Referer": "https://rehametrics.com/",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
            },
            permissions=["storage-access"],
            bypass_csp=True
        )

        paginas.append(await auditar_pagina(context, "Inicio", URL_TARGET, cache_enlaces))
        for nombre, url in PAGINAS:
            paginas.append(await auditar_pagina(context, nombre, url, cache_enlaces))

        await browser.close()

    print("DOCUMENTO: Compilando informe ejecutivo en formato PDF...")
    generar_pdf(paginas)
    generar_resumen(paginas)


def imagen_ajustada(ruta, ancho_max=450, alto_max=520):
    """Imagen escalada para caber en la anchura de la pagina del informe."""
    if not ruta or not os.path.exists(ruta):
        return None
    img = Image(ruta)
    ancho = float(img.drawWidth)
    alto = float(img.drawHeight)
    escala = min(ancho_max / ancho, alto_max / alto, 1.0)
    img.drawWidth = ancho * escala
    img.drawHeight = alto * escala
    return img


def tabla(datos, anchos, cabecera_color='#1E293B'):
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(cabecera_color)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def generar_pdf(paginas):
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = SimpleDocTemplate("informe_auditoria_web.pdf", pagesize=letter)
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18,
                                  textColor=colors.HexColor('#1E293B'))
    sub_style = ParagraphStyle('SubStyle', parent=styles['Heading2'], fontSize=13,
                               textColor=colors.HexColor('#0F172A'), spaceBefore=10, spaceAfter=6)
    body_style = styles['BodyText']
    body_style.fontSize = 9

    # ---------- Portada y resumen global ----------
    story = [
        Paragraph("Informe Tecnico de Auditoria Web", titulo_style),
        Spacer(1, 4),
        Paragraph(f"<b>Sitio Web:</b> {URL_TARGET} | <b>Paginas auditadas:</b> {len(paginas)} | "
                  f"<b>Fecha de ejecucion:</b> {fecha_hoy}", body_style),
        Spacer(1, 15),
    ]

    con_fallo = [p for p in paginas if not isinstance(p["status"], int)]
    total_rotos = [r for p in paginas for r in p["rotos"]]
    errores_unicos = list(dict.fromkeys(e for p in paginas for e in p["errores"]))

    story.append(tabla([
        ["Metrica", "Valor / Estado"],
        ["Paginas auditadas", str(len(paginas))],
        ["Paginas con fallo de carga", str(len(con_fallo))],
        ["Total de enlaces verificados", str(sum(len(p["probados"]) for p in paginas))],
        ["Enlaces no operativos / rotos", str(len(total_rotos))],
        ["Excepciones de JavaScript en consola", str(len(errores_unicos))],
    ], [250, 200]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("Resumen por pagina", sub_style))
    filas = [["Pagina", "HTTP", "Carga (s)", "Enlaces", "Rotos", "Errores JS"]]
    for p in paginas:
        filas.append([
            p["nombre"],
            str(p["status"]),
            f"{p['carga_s']:.1f}",
            str(len(p["probados"])),
            str(len(p["rotos"])),
            str(len(set(p["errores"]))),
        ])
    story.append(tabla(filas, [148, 52, 62, 60, 60, 68]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Cada pagina se detalla en las paginas siguientes con su captura de pantalla, "
        "los enlaces no operativos y los errores de consola.", body_style))

    # ---------- Una seccion por pagina ----------
    for p in paginas:
        story.append(PageBreak())
        story.append(Paragraph(p["nombre"], sub_style))
        story.append(Paragraph(f"<b>URL:</b> {p['url']}", body_style))
        story.append(Spacer(1, 8))

        story.append(tabla([
            ["Metrica", "Valor / Estado"],
            ["Respuesta de carga inicial", f"HTTP {p['status']}"],
            ["Tiempo de carga", f"{p['carga_s']:.1f} s"],
            ["Enlaces verificados", str(len(p["probados"]))],
            ["Enlaces no operativos / rotos", str(len(p["rotos"]))],
            ["Excepciones de JavaScript en consola", str(len(set(p["errores"])))],
        ], [250, 200]))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Auditoria Visual (Vista Escritorio)", ParagraphStyle(
            'Seccion', parent=styles['Heading3'], fontSize=10, textColor=colors.HexColor('#334155'))))
        story.append(Spacer(1, 4))

        img = imagen_ajustada(p["captura_pdf"])
        if img is not None:
            story.append(img)
        else:
            story.append(Paragraph("No se ha podido adjuntar la captura de pantalla.", body_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Enlaces No Operativos", ParagraphStyle(
            'Seccion', parent=styles['Heading3'], fontSize=10, textColor=colors.HexColor('#334155'))))
        if p["rotos"]:
            for r in p["rotos"]:
                story.append(Paragraph(f"• [Estado: {r['status']}] - {r['url']}", body_style))
        else:
            story.append(Paragraph("No se han detectado enlaces rotos en esta pagina.", body_style))

        story.append(Spacer(1, 8))
        story.append(Paragraph("Errores de Consola (JavaScript)", ParagraphStyle(
            'Seccion', parent=styles['Heading3'], fontSize=10, textColor=colors.HexColor('#334155'))))
        if p["errores"]:
            for err in list(dict.fromkeys(p["errores"]))[:6]:
                story.append(Paragraph(f"• {err}", body_style))
        else:
            story.append(Paragraph("Carga ejecutada sin errores de script en el navegador.", body_style))

    doc.build(story)
    print(f"FIN: El informe ha sido generado correctamente: informe_auditoria_web.pdf")


def generar_resumen(paginas):
    """Resumen en texto plano, pensado para publicarlo en Telegram (max. 4096 caracteres)."""
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lineas = [
        "AUDITORIA WEB - " + URL_TARGET,
        f"Fecha: {fecha_hoy}",
        f"Paginas auditadas: {len(paginas)}",
        "",
        "ESTADO POR PAGINA:",
    ]
    for p in paginas:
        lineas.append(
            f"- {p['nombre']}: HTTP {p['status']} | {len(p['probados'])} enlaces | "
            f"{len(p['rotos'])} rotos | {len(set(p['errores']))} errores JS"
        )

    rotos = [(p["nombre"], r) for p in paginas for r in p["rotos"]]
    lineas.append("")
    if rotos:
        lineas.append(f"ENLACES NO OPERATIVOS ({len(rotos)}):")
        for nombre, r in rotos[:20]:
            lineas.append(f"- [{nombre}] [{r['status']}] {r['url']}")
    else:
        lineas.append("Sin enlaces rotos detectados.")

    errores = list(dict.fromkeys(e for p in paginas for e in p["errores"]))
    if errores:
        lineas += ["", "ERRORES DE CONSOLA:"]
        lineas += [f"- {e}" for e in errores[:5]]

    if not any(isinstance(p["status"], int) for p in paginas):
        lineas += ["", "AVISO: la auditoria no ha podido completarse."]

    texto = "\n".join(lineas)
    if len(texto) > 4000:
        texto = texto[:4000] + "\n… (informe completo en el PDF adjunto)"

    with open("resumen.txt", "w", encoding="utf-8") as f:
        f.write(texto + "\n")

    print("RESUMEN: Archivo resumen.txt generado para Telegram.")


if __name__ == "__main__":
    asyncio.run(auditar_web())
