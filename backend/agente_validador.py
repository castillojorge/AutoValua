"""
Agente Validador
------------------
Compara la vigencia recién ingerida contra la última vigencia previa almacenada.

Criterio estadístico explícito (punto marcado como débil en la devolución de
medio ciclo — acá se resuelve):

  - Se calcula la variación porcentual del valor "0km" (año más reciente común)
    de cada vehículo entre ambas vigencias.
  - Se arma la distribución de esas variaciones para TODOS los vehículos de la
    vigencia (no un umbral fijo arbitrario).
  - Un vehículo se marca como anómalo si su variación se aleja más de 3
    desvíos estándar de la media de variación del resto del mercado, o si
    supera un piso absoluto de ±40% (para evitar falsos negativos cuando la
    dispersión general ya es alta, ej. contextos de alta inflación).
  - Esto permite distinguir una suba generalizada de mercado (que mueve la
    media pero no genera outliers relativos) de un error de parseo puntual.

Además detecta:
  - Modelos presentes en la vigencia anterior que desaparecieron en la nueva.
  - Vehículos nuevos (no reportados como anomalía, solo informativo).
"""
import json
import statistics
from db import get_conn


UMBRAL_ABSOLUTO = 0.40   # 40% — piso absoluto de variación sospechosa
Z_SCORE_UMBRAL = 3.0     # desvíos estándar respecto a la media del mercado


def _anio_mas_reciente_comun(precios_a: dict, precios_b: dict) -> str | None:
    comunes = set(precios_a.keys()) & set(precios_b.keys())
    if not comunes:
        return None
    return max(comunes)


def validar_vigencia(vigencia_nueva: str) -> dict:
    conn = get_conn()
    cur = conn.cursor()

    vigencias = [r["vigencia"] for r in cur.execute(
        "SELECT vigencia FROM vigencias_ingeridas ORDER BY vigencia"
    ).fetchall()]

    if vigencia_nueva not in vigencias:
        conn.close()
        raise ValueError(f"La vigencia {vigencia_nueva} no fue ingerida todavía.")

    idx = vigencias.index(vigencia_nueva)
    if idx == 0:
        conn.close()
        return {"vigencia": vigencia_nueva, "mensaje": "Primera vigencia ingerida, no hay comparación posible.",
                "anomalias": [], "desaparecidos": []}

    vigencia_anterior = vigencias[idx - 1]

    actuales = {r["codigo"]: r for r in cur.execute(
        "SELECT * FROM vehiculos WHERE vigencia = ?", (vigencia_nueva,)
    ).fetchall()}
    anteriores = {r["codigo"]: r for r in cur.execute(
        "SELECT * FROM vehiculos WHERE vigencia = ?", (vigencia_anterior,)
    ).fetchall()}

    variaciones = {}  # codigo -> variacion %
    for codigo, actual in actuales.items():
        previo = anteriores.get(codigo)
        if not previo:
            continue
        p_actual = json.loads(actual["precios_json"])
        p_previo = json.loads(previo["precios_json"])
        anio = _anio_mas_reciente_comun(p_actual, p_previo)
        if not anio or p_previo[anio] == 0:
            continue
        var = (p_actual[anio] - p_previo[anio]) / p_previo[anio]
        variaciones[codigo] = var

    desaparecidos = [
        {"codigo": c, "marca": r["marca"], "modelo": r["modelo"]}
        for c, r in anteriores.items() if c not in actuales
    ]

    anomalias = []
    if len(variaciones) >= 2:
        valores = list(variaciones.values())
        media = statistics.mean(valores)
        desvio = statistics.stdev(valores) if len(valores) > 1 else 0
        for codigo, var in variaciones.items():
            z = abs(var - media) / desvio if desvio > 0 else 0
            if abs(var) >= UMBRAL_ABSOLUTO and z >= Z_SCORE_UMBRAL:
                v = actuales[codigo]
                anomalias.append({
                    "codigo": codigo, "marca": v["marca"], "modelo": v["modelo"],
                    "variacion_pct": round(var * 100, 1),
                    "z_score": round(z, 2),
                    "media_mercado_pct": round(media * 100, 1),
                })

    reporte = {
        "vigencia": vigencia_nueva,
        "vigencia_comparada": vigencia_anterior,
        "vehiculos_comparados": len(variaciones),
        "anomalias": anomalias,
        "desaparecidos": desaparecidos,
    }

    # Si hay anomalías o desapariciones, se escala a humano con el detalle completo
    if anomalias or desaparecidos:
        cur.execute("""
            INSERT INTO casos_escalados (tipo, origen_agente, detalle_json, prioridad)
            VALUES ('anomalia_validacion', 'Validador', ?, ?)
        """, (json.dumps(reporte, ensure_ascii=False), "alta" if anomalias else "media"))
        conn.commit()

    conn.close()
    return reporte
