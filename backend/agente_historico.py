"""
Agente Analista Histórico
---------------------------
Arma la serie temporal de un vehículo (mismo código) a través de las
vigencias ingeridas, y calcula variación absoluta y porcentual entre la
primera y la última vigencia disponible para ese modelo.
"""
import json
from db import get_conn


def serie_historica(codigo: str) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    filas = cur.execute(
        "SELECT * FROM vehiculos WHERE codigo = ? ORDER BY vigencia", (codigo,)
    ).fetchall()
    conn.close()

    if not filas:
        return {"resultado": "no_encontrado", "codigo": codigo}

    serie = []
    for f in filas:
        precios = json.loads(f["precios_json"])
        anio_reciente = max(precios.keys())
        serie.append({
            "vigencia": f["vigencia"],
            "anio_valor": anio_reciente,
            "valor": precios[anio_reciente],
        })

    variacion = None
    if len(serie) >= 2:
        primero, ultimo = serie[0]["valor"], serie[-1]["valor"]
        variacion = {
            "absoluta": ultimo - primero,
            "porcentual": round((ultimo - primero) / primero * 100, 1) if primero else None,
        }

    return {
        "resultado": "ok",
        "codigo": codigo,
        "marca": filas[0]["marca"],
        "modelo": filas[0]["modelo"],
        "serie": serie,
        "variacion": variacion,
    }
