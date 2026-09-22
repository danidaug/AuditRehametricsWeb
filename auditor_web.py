import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

URL_TARGET = "https://rehametrics.com"

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
        // Cargar todas las imagenes estándar y sus atributos dataset
        document.querySelectorAll('img').forEach(img => {
            img.removeAttribute('loading');
            if (img.dataset.src) img.src = img.dataset.src;
            if (img.dataset.srcset) img.srcset = img.dataset.srcset;
            if (img.dataset.lazySrc) img.src = img.dataset.lazySrc;
        });

        // Forzar backgrounds en contenedores de WordPress/Elementor
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

        // Asegurar visibilidad de iFrames y reproductores
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

async def auditar_web():
    print(f"INICIO: Iniciando auditoria tecnica del sitio {URL_TARGET}...")
    
    enlaces_probados = []
    enlaces_rotos = []
    errores_consola = []
    
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
        
        # Inyectamos User-Agent real y Referer para evitar el bloqueo HTTP 403 en imagenes/CDNs
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            extra_http_headers={
                "Referer": "https://rehametrics.com/",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
            },
            permissions=["storage-access"],
            bypass_csp=True
        )
        page = await context.new_page()

        # Filtrar avisos triviales de CSP y permisos de consola para no contaminar el informe
        page.on("console", lambda msg: errores_consola.append(msg.text) 
                if msg.type == "error" and "Content Security Policy" not in msg.text and "requestStorageAccess" not in msg.text else None)

        print("ESTADO: Cargando la pagina principal...")
        status_code = "N/A"
        try:
            res_main = await page.goto(URL_TARGET, wait_until="networkidle", timeout=30000)
            status_code = res_main.status if res_main else "N/A"
        except Exception as e:
            # 'networkidle' es estricto: si el sitio mantiene conexiones abiertas (analytics,
            # websockets) agotamos el tiempo. Reintentamos con un criterio mas laxo.
            print(f"AVISO: Espera de red inactiva agotada ({type(e).__name__}). Reintentando con 'load'...")
            try:
                res_main = await page.goto(URL_TARGET, wait_until="load", timeout=60000)
                status_code = res_main.status if res_main else "N/A"
            except Exception as e2:
                print(f"ERROR: No se pudo cargar la pagina principal. Detalle: {e2}")
                await browser.close()
                generar_resumen("Timeout / No responde", [], [], [str(e2)])
                return

        await preparar_pagina_y_multimedia(page)

        print("CAPTURA: Generando captura de pantalla (Desktop)...")
        await page.screenshot(path="screenshot_desktop.png", full_page=True)

        hrefs = await page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
        links_unicos = list(set([h for h in hrefs if h and h.startswith("http")]))
        
        print(f"ANALISIS: Analizando estado de {len(links_unicos)} enlaces extraidos...")
        for link in links_unicos[:10]:
            try:
                test_page = await context.new_page()
                res = await test_page.goto(link, wait_until="domcontentloaded", timeout=10000)
                code = res.status if res else 0
                enlaces_probados.append({"url": link, "status": code})
                if code >= 400 or code == 0:
                    enlaces_rotos.append({"url": link, "status": code})
                await test_page.close()
            except Exception:
                enlaces_probados.append({"url": link, "status": "Error de Conexion"})
                enlaces_rotos.append({"url": link, "status": "Timeout / No responde"})

        await browser.close()

    print("DOCUMENTO: Compilando informe ejecutivo en formato PDF...")
    generar_pdf(status_code, enlaces_probados, enlaces_rotos, errores_consola)
    generar_resumen(status_code, enlaces_probados, enlaces_rotos, errores_consola)

def generar_pdf(status_code, probados, rotos, errores):
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = SimpleDocTemplate("informe_auditoria_web.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1E293B'))
    sub_style = ParagraphStyle('SubStyle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#0F172A'), spaceBefore=12)
    body_style = styles['BodyText']

    story = []

    story.append(Paragraph("Informe Tecnico de Auditoria Web", titulo_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Sitio Web:</b> {URL_TARGET} | <b>Fecha de ejecucion:</b> {fecha_hoy}", body_style))
    story.append(Spacer(1, 15))

    data_resumen = [
        ["Metrica", "Valor / Estado"],
        ["Respuesta de carga inicial", f"HTTP {status_code}"],
        ["Total de enlaces verificados", str(len(probados))],
        ["Enlaces no operativos / rotos", str(len(rotos))],
        ["Excepciones de JavaScript en consola", str(len(errores))]
    ]
    t_resumen = Table(data_resumen, colWidths=[220, 200])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(t_resumen)
    story.append(Spacer(1, 15))

    story.append(Paragraph("Auditoria Visual de Interfaz (Vista Escritorio)", sub_style))
    story.append(Spacer(1, 6))
    try:
        img = Image("screenshot_desktop.png")
        
        ancho_deseado = 450
        factor_escala = ancho_deseado / float(img.drawWidth)
        alto_calculado = float(img.drawHeight) * factor_escala
        
        if alto_calculado > 400:
            img.drawHeight = 400
            img.drawWidth = float(img.drawWidth) * (400 / alto_calculado)
        else:
            img.drawWidth = ancho_deseado
            img.drawHeight = alto_calculado

        story.append(img)
    except Exception as e:
        story.append(Paragraph(f"No se pudo adjuntar la captura de pantalla: {e}", body_style))

    story.append(Spacer(1, 15))
    story.append(Paragraph("Registro de Enlaces No Operativos", sub_style))
    if rotos:
        for r in rotos:
            story.append(Paragraph(f"• [Estado: {r['status']}] - {r['url']}", body_style))
    else:
        story.append(Paragraph("No se han detectado inconsistencias ni errores en los enlaces inspeccionados.", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Registro de Consola (JavaScript)", sub_style))
    if errores:
        errores_unicos = list(dict.fromkeys(errores))
        for err in errores_unicos[:5]:
            story.append(Paragraph(f"• {err}", body_style))
    else:
        story.append(Paragraph("Carga ejecutada sin errores de script en el navegador.", body_style))

    doc.build(story)
    print("FIN: El informe ha sido generado correctamente: informe_auditoria_web.pdf")

def generar_resumen(status_code, probados, rotos, errores):
    """Resumen en texto plano, pensado para publicarlo en Telegram."""
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    errores_unicos = list(dict.fromkeys(errores))

    lineas = [
        "AUDITORIA WEB - " + URL_TARGET,
        "Fecha: " + fecha_hoy,
        "",
        f"HTTP de carga inicial: {status_code}",
        f"Enlaces verificados: {len(probados)}",
        f"Enlaces no operativos: {len(rotos)}",
        f"Errores de consola (JS): {len(errores_unicos)}",
    ]

    if rotos:
        lineas += ["", "Enlaces no operativos:"]
        lineas += [f"- [{r['status']}] {r['url']}" for r in rotos[:15]]
    else:
        lineas += ["", "Sin enlaces rotos detectados."]

    if errores_unicos:
        lineas += ["", "Errores de consola:"]
        lineas += [f"- {e}" for e in errores_unicos[:5]]

    if not probados and not rotos:
        lineas += ["", "AVISO: la auditoria no ha podido completarse."]

    with open("resumen.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")

    print("RESUMEN: Archivo resumen.txt generado para Telegram.")

if __name__ == "__main__":
    asyncio.run(auditar_web())