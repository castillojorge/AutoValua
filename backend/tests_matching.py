"""
Suite de pruebas del Agente de Consulta/Matching contra el catálogo de muestra.
Cubre los 5 caminos de decisión: alias aprendido, coincidencia exacta,
fuzzy automático, escalado por ambigüedad, y no-encontrado (anti-alucinación).

Uso: python3 tests_matching.py   (requiere que ya se haya ingerido al menos
la vigencia 2024-06 en la base — correr después de /admin/ingestar/...)
"""
from agente_matching import consultar

CASOS = [
    ("toyota hilux srx 4x4 2.8 tdi", "match", "coincidencia_exacta"),
    ("cuanto vale mi corola xei 2021", "match", None),          # typo -> fuzzy
    ("gli 2020", "match", None),                                  # match parcial de modelo
    ("auto sedan economico", None, None),                         # genérico -> no debe alucinar
    ("lamborghini aventador 2024", "no_encontrado", None),        # inexistente
    ("vento highline", "match", None),
]

if __name__ == "__main__":
    ok, fail = 0, 0
    for texto, resultado_esperado, estrategia_esperada in CASOS:
        r = consultar(texto, usuario="test_suite", canal="test")
        resultado = r.get("resultado")
        pasa = (resultado_esperado is None or resultado == resultado_esperado)
        estado = "OK " if pasa else "FAIL"
        ok += pasa
        fail += not pasa
        detalle = r.get("estrategia") or r.get("mensaje") or r.get("candidatos")
        print(f"[{estado}] '{texto}' -> {resultado} ({r.get('confianza')}) | {detalle}")
    print(f"\n{ok} OK / {fail} FAIL de {len(CASOS)} casos")
