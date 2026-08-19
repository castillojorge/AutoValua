"""
Agente Ingestor
----------------
Descarga (en este prototipo: lee del disco, simulando lo que el Agente Scraper
ya detectó y bajó) el archivo de una vigencia y lo normaliza a la estructura
tabular interna (memoria semántica).

Soporta DOS formatos de entrada:
  - .json — estructura normalizada de muestra (usada en el prototipo original).
  - .pdf  — el PDF REAL de la DNRPA (formato Excel-export, ~217 páginas). Se
    parsea con dnrpa_parser.py, que resuelve a nivel de carácter los defectos
    de layout reales encontrados en el archivo oficial (columnas de precio
    pegadas sin espacio, texto de modelo largo que se superpone físicamente
    con la columna de carrocería — ver docstring de dnrpa_parser.py).

Las filas que el parser no pudo interpretar con confianza (revisar_layout=True)
se ingieren igual con el mejor texto disponible, pero además generan un caso
escalado al equipo humano — consistente con el diseño original: ante una
ambigüedad de formato, el sistema no adivina, la deriva.
"""
import json
import os
from db import get_conn
import dnrpa_parser


class LayoutError(Exception):
    """Se dispara si el archivo de entrada no respeta el layout esperado.
    Simula la detección de un cambio de formato del PDF de la DNRPA."""
    pass


CAMPOS_REQUERIDOS = {"codigo", "tipo", "marca", "modelo", "precios"}


def ingerir_vigencia(path_archivo: str, vigencia_param: str = None) -> dict:
    ext = os.path.splitext(path_archivo)[1].lower()
    if ext == ".pdf":
        return _ingerir_pdf(path_archivo, vigencia_param)
    return _ingerir_json(path_archivo)


def _ingerir_json(path_archivo: str) -> dict:
    with open(path_archivo, "r", encoding="utf-8") as f:
        data = json.load(f)

    vigencia = data.get("vigencia")
    fuente = data.get("fuente", "desconocida")
    vehiculos = data.get("vehiculos", [])

    if not vigencia or not vehiculos:
        raise LayoutError("El archivo no contiene 'vigencia' o 'vehiculos' — layout inesperado.")

    for v in vehiculos:
        faltantes = CAMPOS_REQUERIDOS - set(v.keys())
        if faltantes:
            raise LayoutError(f"Fila con campos faltantes ({faltantes}): {v.get('codigo', '???')}")

    conn = get_conn()
    cur = conn.cursor()
    ya_ingerida = cur.execute(
        "SELECT 1 FROM vigencias_ingeridas WHERE vigencia = ?", (vigencia,)
    ).fetchone()

    for v in vehiculos:
        _insertar_vehiculo(cur, vigencia, v)

    cur.execute("""
        INSERT INTO vigencias_ingeridas (vigencia, fuente, cantidad_vehiculos)
        VALUES (?, ?, ?)
        ON CONFLICT(vigencia) DO UPDATE SET cantidad_vehiculos=excluded.cantidad_vehiculos
    """, (vigencia, fuente, len(vehiculos)))

    conn.commit()
    conn.close()

    return {"vigencia": vigencia, "vehiculos_ingeridos": len(vehiculos), "ya_existia": bool(ya_ingerida),
            "filas_a_revisar": 0}


def _ingerir_pdf(path_archivo: str, vigencia_param: str = None) -> dict:
    conn = get_conn()
    cur = conn.cursor()

    vigencia = vigencia_param
    total = 0
    revisar_total = 0
    ya_ingerida = None

    with __import__("pdfplumber").open(path_archivo) as pdf:
        # La vigencia real figura en el encabezado de cada página ("Vigencia DD/MM/AAAA")
        if not vigencia:
            primera = pdf.pages[0].extract_text() or ""
            import re
            m = re.search(r"Vigencia\s+(\d{2})/(\d{2})/(\d{4})", primera)
            if m:
                dd, mm, aaaa = m.groups()
                vigencia = f"{aaaa}-{mm}-{dd}"
            else:
                raise LayoutError("No se pudo detectar la vigencia en el encabezado del PDF — layout inesperado.")

        ya_ingerida = cur.execute(
            "SELECT 1 FROM vigencias_ingeridas WHERE vigencia = ?", (vigencia,)
        ).fetchone()

        for page in pdf.pages:
            rows = dnrpa_parser.parse_page(page)
            for v in rows:
                _insertar_vehiculo(cur, vigencia, v)
                total += 1
                if v.get("revisar_layout"):
                    revisar_total += 1
                    cur.execute("""
                        INSERT INTO casos_escalados (tipo, origen_agente, detalle_json, prioridad)
                        VALUES ('revision_layout_ingesta', 'Ingestor', ?, 'baja')
                    """, (json.dumps({
                        "vigencia": vigencia, "codigo": v["codigo"],
                        "texto_sin_interpretar": v["modelo"],
                        "motivo": "No se encontró una carrocería conocida para separar modelo/carrocería.",
                    }, ensure_ascii=False),))
            page.flush_cache()

    cur.execute("""
        INSERT INTO vigencias_ingeridas (vigencia, fuente, cantidad_vehiculos)
        VALUES (?, ?, ?)
        ON CONFLICT(vigencia) DO UPDATE SET cantidad_vehiculos=excluded.cantidad_vehiculos
    """, (vigencia, "DNRPA (PDF oficial)", total))

    conn.commit()
    conn.close()

    return {
        "vigencia": vigencia, "vehiculos_ingeridos": total, "ya_existia": bool(ya_ingerida),
        "filas_a_revisar": revisar_total,
    }


def _insertar_vehiculo(cur, vigencia, v: dict):
    cur.execute("""
        INSERT INTO vehiculos (vigencia, codigo, tipo, marca, modelo, carroceria, precios_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(vigencia, codigo) DO UPDATE SET
            tipo=excluded.tipo, marca=excluded.marca, modelo=excluded.modelo,
            carroceria=excluded.carroceria, precios_json=excluded.precios_json
    """, (vigencia, v["codigo"], v["tipo"], v["marca"].upper(), v["modelo"].upper(),
          v.get("carroceria", ""), json.dumps(v["precios"])))
