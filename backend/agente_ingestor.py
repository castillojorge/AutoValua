"""
Agente Ingestor
----------------
Descarga (en este prototipo: lee del disco, simulando lo que el Agente Scraper
ya detectó y bajó) el archivo de una vigencia y lo normaliza a la estructura
tabular interna (memoria semántica).

En producción este agente reemplazaría la lectura de disco por el parseo real
del PDF de 212 páginas de la DNRPA (filas de ancho fijo). Acá se mantiene el
mismo contrato de salida para que el resto del sistema sea agnóstico a la
fuente.
"""
import json
from db import get_conn


class LayoutError(Exception):
    """Se dispara si el archivo de entrada no respeta el layout esperado.
    Simula la detección de un cambio de formato del PDF de la DNRPA."""
    pass


CAMPOS_REQUERIDOS = {"codigo", "tipo", "marca", "modelo", "precios"}


def ingerir_vigencia(path_archivo: str) -> dict:
    with open(path_archivo, "r", encoding="utf-8") as f:
        data = json.load(f)

    vigencia = data.get("vigencia")
    fuente = data.get("fuente", "desconocida")
    vehiculos = data.get("vehiculos", [])

    if not vigencia or not vehiculos:
        raise LayoutError("El archivo no contiene 'vigencia' o 'vehiculos' — layout inesperado.")

    # Validación de layout: cada fila debe tener los campos esperados
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
        cur.execute("""
            INSERT INTO vehiculos (vigencia, codigo, tipo, marca, modelo, carroceria, precios_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vigencia, codigo) DO UPDATE SET
                tipo=excluded.tipo, marca=excluded.marca, modelo=excluded.modelo,
                carroceria=excluded.carroceria, precios_json=excluded.precios_json
        """, (vigencia, v["codigo"], v["tipo"], v["marca"].upper(), v["modelo"].upper(),
              v.get("carroceria", ""), json.dumps(v["precios"])))

    cur.execute("""
        INSERT INTO vigencias_ingeridas (vigencia, fuente, cantidad_vehiculos)
        VALUES (?, ?, ?)
        ON CONFLICT(vigencia) DO UPDATE SET cantidad_vehiculos=excluded.cantidad_vehiculos
    """, (vigencia, fuente, len(vehiculos)))

    conn.commit()
    conn.close()

    return {
        "vigencia": vigencia,
        "vehiculos_ingeridos": len(vehiculos),
        "ya_existia": bool(ya_ingerida),
    }
