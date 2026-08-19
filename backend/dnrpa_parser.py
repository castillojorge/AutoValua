"""
Parser real del PDF de valuaciones DNRPA (formato Excel-export, 217 páginas).

Resuelve 2 problemas reales encontrados al parsear el archivo real (no presentes
en los datos de muestra, y que la devolución de medio ciclo había anticipado
como riesgo bajo el nombre de "cambio de layout"):

1. Columnas de precio adyacentes sin espacio entre sí cuando ambos valores son
   largos (ej. "0km" y el año más reciente quedan pegados: "10853271092235000").
   Se resuelve extrayendo a nivel de CARÁCTER y agrupando por gaps de posición X,
   no por "palabras" pre-tokenizadas.

2. Cuando la descripción del modelo es muy larga, su texto se superpone
   físicamente con la columna "Desc. Tipo" en el PDF fuente (no es un error de
   parseo: el PDF de origen tiene ese defecto). Ordenar caracteres por posición X
   produce texto entreverado ("QUATTRSOEDAN" en vez de "QUATTROSEDAN"). Se
   resuelve preservando el ORDEN NATURAL del stream del PDF (que sí es correcto)
   en vez de reordenar por X, y separando modelo/carrocería con un diccionario
   de carrocerías conocidas de la DNRPA en vez de con un límite de columna fijo.

Filas donde ninguna carrocería conocida matchea quedan con revisar_layout=True,
consistente con el diseño original: el Validador escala a un humano en vez de
adivinar.
"""
import pdfplumber
import re
import json
import sys
import time

TEXT_START_X = 94   # inicio de "Desc. marca"
PRICE_START_X = 223  # a partir de acá son columnas de precio (0km...2002)
CODE_RE = re.compile(r"^\d{8}$")
GAP_THRESHOLD = 1.2  # px — separa números/palabras pegadas sin colapsar dígitos de un mismo número

YEAR_HEADERS = [("0km", 231)] + [(str(y), 253 + (2025 - y) * 22) for y in range(2025, 2001, -1)]

# Vocabulario de carrocerías DNRPA, relevado empíricamente del propio archivo
# (ver informe/tools/relevar_vocabulario.py). Ordenado por longitud descendente
# para preferir el matching más específico primero.
CARROCERIAS = sorted([
    "TODO TERRENO", "CUATRICICLO", "MOTOCICLETA", "SEDAN 4 PUERTAS",
    "CHASIS C/CABINA DORMITORIO", "CHASIS C/CABINA", "CHASIS CON CABINA",
    "CHASIS SIN CABINA", "RURAL 5 PUERTAS", "RURAL 4/5 PUERTAS",
    "CAMION", "SEDAN 5 PUERTAS", "FURGON", "TRACTOR DE CARRETERA",
    "TRACTOR C/CABINA DORMITORIO", "SIN ESPECIFICACION", "SEDAN 3 PUERTAS",
    "SEDAN 2 PUERTAS", "RURAL 3 PUERTAS", "FAMILIAR", "SCOOTER",
    "PICK-UP CABINA DOBLE", "PICK-UP CABINA SIMPLE", "PICK-UP CABINA Y MEDIA",
    "PICK-UP", "COUPE", "CONVERTIBLE", "TRANS.DE PASAJEROS", "DESCAPOTABLE",
    "UTILITARIO", "FURGONETA", "ARENERO", "CICLOMOTOR", "TRICICLO",
    "PICK-UP CARROZADA",
], key=len, reverse=True)


def nearest_year(center):
    name, x = min(YEAR_HEADERS, key=lambda h: abs(h[1] - center))
    return name, abs(x - center)


def cluster_by_gap(items, gap_threshold, key_x0, key_x1, key_text):
    """Agrupa items ordenados por posición X en clusters separados por gaps > threshold."""
    clusters, cur, last_x1 = [], [], None
    for it in items:
        x0 = key_x0(it)
        if last_x1 is not None and (x0 - last_x1) > gap_threshold:
            clusters.append(cur)
            cur = []
        cur.append(it)
        last_x1 = key_x1(it)
    if cur:
        clusters.append(cur)
    return clusters


def split_modelo_carroceria(blob):
    """Separa el texto combinado modelo+carrocería usando el vocabulario conocido.
    Devuelve (modelo, carroceria, revisar_layout)."""
    blob = re.sub(r"\s+", " ", blob).strip()
    for carr in CARROCERIAS:
        # caso limpio: carrocería al final, precedida de espacio
        suffix = " " + carr
        if blob.endswith(suffix):
            return blob[: -len(suffix)].strip(), carr, False
        if blob == carr:
            return "", carr, False
        # caso pegado (sin espacio): buscar la carrocería como sufijo directo
        if blob.endswith(carr) and len(blob) > len(carr):
            return blob[: -len(carr)].strip(), carr, False
    # ninguna carrocería conocida matcheó: no se puede separar con confianza
    return blob, "", True


def parse_page(page):
    words = page.extract_words()
    chars = page.chars
    # Ancla de fila: columna I/N (x0 18-22, texto 'I' o 'N'). Es la única
    # columna que se mantiene 100% consistente en formato — el código
    # MTM/FMM en cambio no siempre es 8 dígitos puros (hay códigos con
    # prefijo de letra como "Q4910016" y códigos de 7 dígitos), así que
    # anclar por regex de 8 dígitos perdía esas filas y las fusionaba con
    # la fila anterior.
    anchors = sorted(
        [w for w in words if w["top"] >= 60 and 18 <= w["x0"] < 23 and w["text"] in ("I", "N")],
        key=lambda w: w["top"],
    )
    # Techo de la fila: recorta el pie de página ("Página X de 217") para que
    # no se filtre dentro del último renglón de la página.
    footer_words = [w for w in words if "gina" in w["text"] or w["text"] == "Página"]
    footer_top = min((w["top"] for w in footer_words), default=1e9)

    rows = []
    for i, a in enumerate(anchors):
        top0 = a["top"] - 1
        top1 = anchors[i + 1]["top"] - 1 if i + 1 < len(anchors) else footer_top - 1
        top1 = min(top1, footer_top - 1)

        codigo_words = [w["text"] for w in words if top0 <= w["top"] < top1 and 26 <= w["x0"] < 47]
        tipo_words = [w["text"] for w in words if top0 <= w["top"] < top1 and 47 <= w["x0"] < 55]
        marca_words = [w["text"] for w in words if top0 <= w["top"] < top1 and 94 <= w["x0"] < 129]

        # Todos los caracteres desde la columna Modelo hasta el final de la fila
        # (129..800), sin límite fijo hacia la derecha: la clasificación
        # texto/precio se hace por CONTENIDO (dígitos vs. letras) + cercanía
        # a una columna de año real, no por posición X fija — esto evita
        # cortar carrocerías largas que físicamente se extienden dentro de lo
        # que en otras filas es zona de precios.
        row_chars_all = [c for c in chars if top0 <= c["top"] < top1 and c["x0"] >= 129]

        # 1) Precios: se identifican ordenando por X y agrupando por gaps
        #    (ver docstring — necesario porque valores adyacentes largos a
        #    veces quedan pegados sin espacio entre columnas). Solo se aceptan
        #    clusters de 5+ dígitos que caen a menos de 15px de una columna de
        #    año real, para no confundir números cortos de la ficha técnica
        #    (ej. "1730" en un nombre de camión) con precios.
        price_zone_chars = sorted([c for c in row_chars_all if c["x0"] >= 129], key=lambda c: c["x0"])
        clusters = cluster_by_gap(price_zone_chars, GAP_THRESHOLD, lambda c: c["x0"], lambda c: c["x1"], lambda c: c["text"])
        precios = {}
        price_strings_found = []
        for cluster in clusters:
            text = "".join(c["text"] for c in cluster)
            if text.isdigit() and len(text) >= 5:
                center = (cluster[0]["x0"] + cluster[-1]["x1"]) / 2
                year, dist = nearest_year(center)
                if dist <= 15:
                    precios[year] = int(text)
                    price_strings_found.append(text)

        # 2) Texto (modelo+carrocería): orden NATURAL de stream (no resortear
        #    por X — ver docstring, evita entreverado de caracteres
        #    superpuestos), quitando después las cadenas de precio ya
        #    identificadas en el paso 1 si quedaron incluidas.
        text_blob = "".join(c["text"] for c in row_chars_all)
        for ps in price_strings_found:
            text_blob = text_blob.replace(ps, "", 1)
        modelo, carroceria, revisar = split_modelo_carroceria(text_blob)

        rows.append({
            "codigo": (codigo_words[0] if codigo_words else f"SIN_CODIGO_top{round(a['top'])}"),
            "tipo": (tipo_words[0] if tipo_words else "A"),
            "marca": " ".join(marca_words).strip(),
            "modelo": modelo,
            "carroceria": carroceria,
            "precios": precios,
            "revisar_layout": revisar,
        })
    return rows


def parse_pdf(path, vigencia=None, fuente="DNRPA (PDF oficial)", progress=True):
    vehiculos = []
    revisar_count = 0
    t0 = time.time()
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            rows = parse_page(page)
            vehiculos.extend(rows)
            revisar_count += sum(1 for r in rows if r["revisar_layout"])
            page.flush_cache()
            page.get_textmap.cache_clear() if hasattr(page, "get_textmap") else None
            if progress and (i + 1) % 25 == 0:
                print(f"  ...{i+1}/{n} páginas, {len(vehiculos)} filas acumuladas, {time.time()-t0:.1f}s", file=sys.stderr)
    return {
        "vigencia": vigencia or "desconocida",
        "fuente": fuente,
        "vehiculos": vehiculos,
        "_meta": {"total_filas": len(vehiculos), "filas_a_revisar": revisar_count, "tiempo_seg": round(time.time() - t0, 1)},
    }


def parse_pdf_streaming(path, out_path, vigencia=None, fuente="DNRPA (PDF oficial)", progress=True):
    """Escribe cada fila a un archivo JSONL a medida que se procesa, para
    mantener memoria acotada en documentos grandes (217 páginas)."""
    import gc
    total, revisar_count = 0, 0
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as out, pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i in range(n):
            page = pdf.pages[i]
            rows = parse_page(page)
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
            total += len(rows)
            revisar_count += sum(1 for r in rows if r["revisar_layout"])
            page.flush_cache()
            pdf.pages[i] = None  # liberar referencia
            del page, rows
            if (i + 1) % 20 == 0:
                gc.collect()
            if progress and (i + 1) % 25 == 0:
                print(f"  ...{i+1}/{n} páginas, {total} filas, {time.time()-t0:.1f}s", file=sys.stderr)
    return {"total_filas": total, "filas_a_revisar": revisar_count, "tiempo_seg": round(time.time() - t0, 1),
            "vigencia": vigencia, "fuente": fuente}


if __name__ == "__main__":
    path = sys.argv[1]
    out_jsonl = sys.argv[3] if len(sys.argv) > 3 else "/tmp/vigencia_real.jsonl"
    meta = parse_pdf_streaming(path, out_jsonl, vigencia=sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(meta, indent=2))
