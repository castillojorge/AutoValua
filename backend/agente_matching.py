"""
Agente de Consulta / Matching
--------------------------------
Resuelve el punto más señalado como "caja negra" en la devolución de medio
ciclo: acá el fuzzy search queda completamente especificado.

Algoritmo: rapidfuzz.fuzz.token_set_ratio (Levenshtein normalizado sobre el
conjunto de tokens, insensible a orden y a palabras repetidas). Se descartó
WRatio en la implementación: su heurística de partial-ratio infla el score
cuando la consulta es un substring corto y genérico dentro de una cadena
larga (ej. "sedan económico" puntuaba 85.5 contra "TOYOTA COROLLA... SEDAN 4P"
solo por compartir la palabra "SEDAN"). token_set_ratio resultó más robusto
para este caso de uso y bajó ese mismo caso a ~35 puntos.

Umbrales de confianza (0-100), calibrados empíricamente contra el catálogo de
muestra (ver /home/claude/autovalua/backend/tests_matching.py):
  - >= 80  -> match automático, se responde directo al usuario.
  - 60-79  -> ambiguo: se cambia de estrategia (segundo intento variando el
              criterio de búsqueda). Si el segundo intento tampoco supera 80,
              se escala a humano con los candidatos y sus scores.
  - < 60   -> no hay coincidencia razonable. Regla anti-alucinación: se
              responde "no encontrado", nunca se estima un valor.

Ciclo de planificación (ReAct aplicado a esta consulta puntual):
  1) Memoria procedimental (alias ya aprendidos) — intento más barato y de
     mayor confianza posible, siempre se prueba primero.
  2) Coincidencia exacta marca+modelo.
  3) Fuzzy search sobre "marca + modelo + carrocería" concatenados (estrategia 1).
  4) Si no supera el umbral: fuzzy search solo sobre "modelo" sin marca,
     para cubrir el caso en que el usuario se equivocó de marca pero no de
     modelo (estrategia 2 — "variar el criterio").
  5) Si ninguna estrategia supera el umbral automático -> escalar a humano.
"""
import re
import json
from rapidfuzz import fuzz, process
from db import get_conn

UMBRAL_AUTOMATICO = 80
UMBRAL_MINIMO = 60

_ANIO_RE = re.compile(r"\b(19|20)\d{2}\b")

# Palabras de relleno frecuentes en la consulta en lenguaje natural que no
# aportan señal al fuzzy matching y diluyen el score si se comparan tal cual.
_STOPWORDS = {
    "CUANTO", "CUANTO?", "VALE", "MI", "EL", "LA", "UN", "UNA", "DE", "DEL",
    "POR", "CONSULTAR", "VALOR", "TENGO", "QUIERO", "SABER", "ME", "PODES",
    "DECIR", "PRECIO", "CUAL", "ES", "TIENE", "QUE",
}


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.strip().upper())


def _quitar_relleno(texto: str) -> str:
    tokens = [t for t in texto.split() if t not in _STOPWORDS]
    return " ".join(tokens) if tokens else texto


def _extraer_anio(texto: str):
    m = _ANIO_RE.search(texto)
    return m.group(0) if m else None


def _texto_libre_sin_anio(texto: str) -> str:
    return _ANIO_RE.sub("", texto).strip()


def _catalogo_vigencia(cur, vigencia: str):
    if vigencia is None:
        row = cur.execute("SELECT vigencia FROM vigencias_ingeridas ORDER BY vigencia DESC LIMIT 1").fetchone()
        if not row:
            return None, []
        vigencia = row["vigencia"]
    filas = cur.execute("SELECT * FROM vehiculos WHERE vigencia = ?", (vigencia,)).fetchall()
    return vigencia, filas


def consultar(texto_usuario: str, usuario: str = "anonimo", canal: str = "chatbot", vigencia: str = None) -> dict:
    conn = get_conn()
    cur = conn.cursor()

    texto_norm = _normalizar(texto_usuario)
    anio = _extraer_anio(texto_norm)
    libre = _quitar_relleno(_normalizar(_texto_libre_sin_anio(texto_norm)))

    vigencia_usada, catalogo = _catalogo_vigencia(cur, vigencia)
    if not catalogo:
        conn.close()
        return {"resultado": "no_encontrado", "motivo": "No hay ninguna vigencia ingerida todavía."}

    resultado_base = {
        "consulta": texto_usuario, "anio_detectado": anio, "vigencia_consultada": vigencia_usada,
    }

    # --- 1) Memoria procedimental: alias ya aprendidos ---
    alias_row = cur.execute("SELECT codigo_resuelto FROM alias WHERE alias_texto = ?", (libre,)).fetchone()
    if alias_row:
        v = next((c for c in catalogo if c["codigo"] == alias_row["codigo_resuelto"]), None)
        if v:
            return _responder_match(cur, conn, v, anio, resultado_base, "alias_aprendido", 100.0, usuario, canal, texto_norm)

    # --- 2) Coincidencia exacta marca + modelo ---
    for v in catalogo:
        combinado = f"{v['marca']} {v['modelo']}"
        if libre == combinado or libre == v["modelo"]:
            return _responder_match(cur, conn, v, anio, resultado_base, "coincidencia_exacta", 100.0, usuario, canal, texto_norm)

    # --- 3) Estrategia 1: fuzzy sobre marca+modelo+carrocería ---
    opciones = {f"{v['marca']} {v['modelo']} {v['carroceria']}": v for v in catalogo}
    match1 = process.extractOne(libre, opciones.keys(), scorer=fuzz.token_set_ratio)

    mejor_v, mejor_score, estrategia = None, 0, None
    if match1:
        mejor_v, mejor_score, estrategia = opciones[match1[0]], match1[1], "fuzzy_marca_modelo"

    # --- 4) Estrategia 2 ("cambiar de estrategia", no repetir la misma búsqueda): fuzzy solo sobre modelo ---
    if mejor_score < UMBRAL_AUTOMATICO:
        opciones_modelo = {v["modelo"]: v for v in catalogo}
        match2 = process.extractOne(libre, opciones_modelo.keys(), scorer=fuzz.token_set_ratio)
        if match2 and match2[1] > mejor_score:
            mejor_v, mejor_score, estrategia = opciones_modelo[match2[0]], match2[1], "fuzzy_solo_modelo"

    # --- 5) Evaluación del resultado ---
    if mejor_v and mejor_score >= UMBRAL_AUTOMATICO:
        return _responder_match(cur, conn, mejor_v, anio, resultado_base, estrategia, mejor_score, usuario, canal, texto_norm)

    if mejor_v and mejor_score >= UMBRAL_MINIMO:
        # Ambiguo tras dos estrategias -> escalar con candidatos (top 3)
        candidatos_raw = process.extract(libre, opciones.keys(), scorer=fuzz.token_set_ratio, limit=3)
        candidatos = [{"opcion": c[0], "score": round(c[1], 1)} for c in candidatos_raw]
        detalle = {**resultado_base, "candidatos": candidatos, "texto_normalizado": libre}
        caso_id = _escalar(cur, conn, "ambiguedad_consulta", "Consulta/Matching", detalle, "media")
        _log_consulta(cur, conn, usuario, canal, texto_norm, estrategia, None, mejor_score, "escalado")
        conn.commit()
        conn.close()
        return {**resultado_base, "resultado": "escalado_a_humano", "caso_id": caso_id, "candidatos": candidatos}

    # --- Anti-alucinación: no hay coincidencia razonable ---
    _log_consulta(cur, conn, usuario, canal, texto_norm, "sin_match", None, mejor_score, "no_encontrado")
    conn.commit()
    conn.close()
    return {**resultado_base, "resultado": "no_encontrado",
            "mensaje": "No se encontró ese vehículo en la tabla oficial vigente. No es posible estimar un valor aproximado."}


def _responder_match(cur, conn, v, anio, base, estrategia, score, usuario, canal, texto_norm):
    precios = json.loads(v["precios_json"])
    anio_usar = anio if (anio and anio in precios) else max(precios.keys())
    _log_consulta(cur, conn, usuario, canal, texto_norm, estrategia, v["codigo"], score, "match")
    conn.commit()
    conn.close()
    return {
        **base, "resultado": "match",
        "estrategia": estrategia, "confianza": round(score, 1),
        "vehiculo": {
            "codigo": v["codigo"], "marca": v["marca"], "modelo": v["modelo"],
            "carroceria": v["carroceria"], "tipo": v["tipo"],
        },
        "anio_valor": anio_usar, "valor": precios.get(anio_usar),
        "vigencia": v["vigencia"],
        "nota_legal": "Este valor es informativo. No reemplaza el trámite formal ante el registro correspondiente.",
    }


def _escalar(cur, conn, tipo, agente, detalle: dict, prioridad: str) -> int:
    cur.execute("""
        INSERT INTO casos_escalados (tipo, origen_agente, detalle_json, prioridad)
        VALUES (?, ?, ?, ?)
    """, (tipo, agente, json.dumps(detalle, ensure_ascii=False), prioridad))
    conn.commit()
    return cur.lastrowid


def _log_consulta(cur, conn, usuario, canal, texto, estrategia, codigo_match, confianza, resultado):
    cur.execute("""
        INSERT INTO consultas_log (usuario, canal, consulta_texto, estrategia, codigo_match, confianza, resultado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (usuario, canal, texto, estrategia, codigo_match, confianza, resultado))
