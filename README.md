# AutoValúa AI

Sistema agéntico que resuelve la fricción de consultar la tabla oficial de
valuaciones de automotores y motovehículos que publica mensualmente la DNRPA
(Argentina) en formato PDF de ~212 páginas. Expone la consulta por dos
canales: un **chatbot conversacional** y una **API REST autenticada** para
integraciones de terceros (aseguradoras, gestorías, tasadores).

> Trabajo práctico — UTN FRBA, Inteligencia Artificial Aplicada a Organizaciones.

## Problema que resuelve

Consultar el valor oficial de un vehículo hoy requiere abrir manualmente un
PDF de cientos de páginas y buscar fila por fila. No existe una vía
estructurada para que sistemas de terceros consulten este dato.

## Arquitectura

6 agentes especializados bajo un orquestador central (FastAPI), siguiendo el
ciclo Observar → Analizar → Planificar → Actuar → Evaluar → Aprender:

| Agente | Responsabilidad |
|---|---|
| **Scraper** | Detecta tablas nuevas publicadas por la DNRPA (simulado en este prototipo: lee archivos locales) |
| **Ingestor** | Parsea el archivo de vigencia a estructura tabular normalizada, valida el layout |
| **Validador** | Compara contra la vigencia anterior, detecta anomalías de precio (criterio: z-score vs. media de mercado + piso absoluto 40%) y modelos desaparecidos |
| **Consulta/Matching** | Interpreta la consulta en lenguaje natural, aplica fuzzy search (`rapidfuzz.token_set_ratio`) con umbrales de confianza explícitos y cambio de estrategia ante resultado insuficiente |
| **Analista Histórico** | Arma series temporales y calcula variación entre vigencias |
| **Notificador** | Configuración de alertas por cambio de valor (endpoint base implementado) |

Memoria persistente en 4 capas: semántica (tablas ingeridas), episódica
(historial de consultas), procedimental (alias aprendidos de casos
escalados) y de notificaciones.

Reglas de diseño explícitas: **anti-alucinación** (si el vehículo no existe,
responde "no encontrado", nunca estima) y **precedencia de la fuente
oficial** (el aprendizaje solo ayuda a identificar el modelo, nunca modifica
su valor).

## Stack

| Componente | Tecnología | Por qué |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Tipado, async nativo, documentación automática (OpenAPI), ideal para exponer el segundo canal (API REST) sin código adicional |
| Matching difuso | rapidfuzz (token_set_ratio) | Más rápido que fuzzywuzzy (implementación en C++), robusto a orden de palabras |
| Base de datos | SQLite | Prototipo de un solo nodo, cero configuración, suficiente para el volumen de este trabajo |
| Frontend | HTML + JS vanilla | Sin build step, servido directo por FastAPI (`StaticFiles`), suficiente para demostrar el flujo completo |
| Despliegue | Render (free tier) | Deploy directo desde GitHub, sin tarjeta de crédito |

## Cómo correrlo localmente

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Abrir `http://localhost:8000` (chatbot) y `http://localhost:8000/admin.html`
(panel administrativo).

**Primer uso:** desde el panel administrativo, sección "Ciclo de ingesta",
hacer clic en "Ingerir" para las vigencias de muestra (`2024-05` y
`2024-06`) — esto ejecuta el Ingestor y dispara al Validador, que va a
detectar una anomalía de precio inyectada a propósito en los datos de
muestra (para demostrar la detección).

## API REST autenticada

```bash
curl -X POST http://localhost:8000/api/v1/consulta \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-autovalua-2024" \
  -d '{"marca":"toyota","modelo":"hilux srx","anio":"2024"}'
```

## Tests

```bash
cd backend
python3 tests_matching.py
```

## Datos

El sistema soporta dos fuentes de datos:

1. **Datos de muestra** (`vigencia_2024_05.json`, `vigencia_2024_06.json`) — 20
   vehículos con formato equivalente al real, usados para demostrar el ciclo
   completo de escalado y aprendizaje con datos controlados.
2. **PDF real de la DNRPA** (`vigencia_2026_08.pdf`, vigencia 01/08/2026,
   217 páginas) — el archivo oficial sin modificar. `dnrpa_parser.py` lo
   parsea a nivel de carácter (no de "palabra" pre-tokenizada), lo cual fue
   necesario para resolver 3 defectos de layout reales encontrados en el
   archivo oficial:
   - Columnas de precio adyacentes pegadas sin espacio entre sí (ej. el valor
     0km y el del año más reciente, cuando ambos son largos).
   - Texto de descripción de modelo muy largo que se superpone físicamente
     con la columna de carrocería en el PDF fuente (no es un error de
     parseo — el PDF de origen tiene ese defecto).
   - Códigos de fila que no son 8 dígitos puros (motos con prefijo de letra
     como "Q4910016", o códigos de 7 dígitos).

   Resultado: **18.180 vehículos ingeridos**, de los cuales ~3% (548 filas,
   mayormente categorías raras como cuatriciclos o motocross) no pudieron
   separarse automáticamente en modelo/carrocería y quedan escalados al
   panel administrativo con el texto sin interpretar — consistente con la
   regla de diseño original: ante una ambigüedad de formato, el sistema no
   adivina, la deriva a un humano.

   Test dedicado: `python3 tests_dnrpa_parser.py data/vigencia_2026_08.pdf`
   (valida 4 filas conocidas contra los valores reales del PDF).
