"""
Tests del parser del PDF real de la DNRPA (dnrpa_parser.py).

A diferencia de tests_matching.py (que prueba el Agente de Consulta contra
datos de muestra), esto valida el parser contra el PDF oficial real
(vigencia 01/08/2026, 217 páginas) — específicamente los 3 defectos de
layout reales que se encontraron y resolvieron:

  1. Columnas de precio adyacentes pegadas sin espacio (ej. 0km + año más
     reciente cuando ambos valores son largos).
  2. Texto de modelo largo que se superpone físicamente con la columna de
     carrocería en el PDF fuente.
  3. Códigos de fila que no son 8 dígitos puros (prefijo de letra, o 7 dígitos)
     — encontrados en motos y vehículos importados.

Uso: python3 tests_dnrpa_parser.py /ruta/al/pdf/real.pdf
"""
import sys
import pdfplumber
import dnrpa_parser as dp

CASOS_CONOCIDOS = [
    # (codigo, marca_esperada, modelo_esperado, carroceria_esperada, año_con_precio, precio_esperado)
    ("01102078", "AUDI", "A4 3.0 QUATTRO", "SEDAN 4 PUERTAS", "2007", 14157000),
    ("01121378", "AUDI", "A5 COUPE 40 TFSI", "COUPE", "0km", 108532710),
    ("01102345", "AUDI", "A6 55 TFSI STRONIC QUATTRO", "SEDAN 4 PUERTAS", "0km", 143572000),
    ("04791166", "FORD", "CARGO 1722", "CHASIS C/CABINA DORMITORIO", "2016", 68068000),
]


def run(pdf_path):
    ok, fail = 0, 0
    with pdfplumber.open(pdf_path) as pdf:
        # Buscar cada código conocido en las primeras ~15 páginas (donde están AUDI/FORD)
        encontrados = {}
        for page in pdf.pages[:60]:
            for r in dp.parse_page(page):
                if r["codigo"] in {c[0] for c in CASOS_CONOCIDOS}:
                    encontrados[r["codigo"]] = r
            page.flush_cache()

        for codigo, marca, modelo, carroceria, anio, precio in CASOS_CONOCIDOS:
            r = encontrados.get(codigo)
            if not r:
                print(f"[FAIL] {codigo} no encontrado en las páginas escaneadas")
                fail += 1
                continue
            checks = [
                r["marca"] == marca,
                r["modelo"] == modelo,
                r["carroceria"] == carroceria,
                r["precios"].get(anio) == precio,
                r["revisar_layout"] is False,
            ]
            if all(checks):
                print(f"[OK ] {codigo} {marca} {modelo} | {carroceria} | {anio}={precio}")
                ok += 1
            else:
                print(f"[FAIL] {codigo} -> {r}")
                fail += 1

    print(f"\n{ok} OK / {fail} FAIL de {len(CASOS_CONOCIDOS)} casos conocidos")
    return fail == 0


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/vigencia_2026_08.pdf"
    success = run(path)
    sys.exit(0 if success else 1)
