const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, AlignmentType, Header, Footer, PageNumber,
  ExternalHyperlink,
} = require("docx");

const IMG = path.join(__dirname, "img");
const DIMS = JSON.parse(fs.readFileSync(path.join(__dirname, "img_dims.json")));
const CONTENT_W = 560;

function dimsFor(file, maxW = CONTENT_W) {
  const [w0, h0] = DIMS[file];
  const w = Math.min(maxW, w0);
  const h = Math.round((w / w0) * h0);
  return { width: w, height: h };
}

function h1(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 } }); }
function h2(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 260, after: 120 } }); }
function p(text, opts = {}) {
  const { size = 22, color = "1E293B", italics = false, bold = false, align = AlignmentType.LEFT } = opts;
  return new Paragraph({ children: [new TextRun({ text, size, color, italics, bold })], spacing: { after: 140 }, alignment: align });
}
function bullet(text, opts = {}) {
  const { size = 22, bold = false } = opts;
  return new Paragraph({ children: [new TextRun({ text, size, bold })], bullet: { level: 0 }, spacing: { after: 70 } });
}
function caption(text) {
  return new Paragraph({ children: [new TextRun({ text, italics: true, size: 18, color: "64748B" })], alignment: AlignmentType.CENTER, spacing: { after: 260 } });
}
function image(file, maxW) {
  const { width, height } = dimsFor(file, maxW);
  return new Paragraph({
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(IMG, file)), transformation: { width, height } })],
    alignment: AlignmentType.CENTER, spacing: { after: 60 },
  });
}
function cell(text, opts = {}) {
  const { bold = false, shade = null, width = null, size = 19, color = "1E293B" } = opts;
  return new TableCell({
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text, bold, size, color })] })],
  });
}
function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((t, i) => cell(t, { bold: true, shade: "1E3A8A", width: widths[i], size: 19, color: "FFFFFF" })) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c, i) => cell(c, { width: widths[i], shade: ri % 2 ? "F1F5F9" : "FFFFFF" })) })),
    ],
  });
}
function linkCell(url) {
  return new TableCell({
    width: { size: 6400, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [new Paragraph({ children: url.startsWith("http")
      ? [new ExternalHyperlink({ link: url, children: [new TextRun({ text: url, style: "Hyperlink", size: 19 })] })]
      : [new TextRun({ text: url, italics: true, color: "9A3412", size: 19 })] })],
  });
}
function linkRow(label, url) {
  return new TableRow({ children: [cell(label, { bold: true, width: 2600, shade: "F1F5F9" }), linkCell(url)] });
}

const PAGE = { size: { width: 11906, height: 16838 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } };
const HEADER = new Header({ children: [p("UTN-FRBA | Inteligencia Artificial Aplicada a Organizaciones — Entrega Final · AutoValúa AI", { size: 16, color: "94A3B8" })] });
const FOOTER = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "94A3B8" })] })] });

const doc = new Document({
  styles: { default: { document: { run: { font: "Calibri", size: 22, color: "1E293B" } } } },
  sections: [
    // ============ PORTADA + LINKS ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        new Paragraph({ text: "AutoValúa AI", heading: HeadingLevel.TITLE, spacing: { after: 100 } }),
        p("Entrega final de proyecto — Inteligencia Artificial Aplicada a Organizaciones", { size: 26, color: "475569" }),
        p("Universidad Tecnológica Nacional · Facultad Regional Buenos Aires", { size: 21, color: "64748B" }),
        p("Jorge Castillo — desarrollo full-stack (arquitectura, backend, agentes, frontend, diagramas)", { size: 21, color: "64748B" }),
        new Paragraph({ text: "", spacing: { after: 220 } }),

        h2("Links obligatorios"),
        p("El docente evaluará directamente en estos links, no en el PDF.", { italics: true, size: 20, color: "64748B" }),
        new Table({
          width: { size: 9000, type: WidthType.DXA }, columnWidths: [2600, 6400],
          rows: [
            new TableRow({ tableHeader: true, children: [cell("Recurso", { bold: true, shade: "1E3A8A", width: 2600, color: "FFFFFF" }), cell("URL", { bold: true, shade: "1E3A8A", width: 6400, color: "FFFFFF" })] }),
            linkRow("Repositorio GitHub", "PENDIENTE — se completa al subir el repo (ver README para los pasos)"),
            linkRow("Aplicación web en producción", "PENDIENTE — se completa al deployar en Render (ver README)"),
            linkRow("Video de demo", "PENDIENTE — opcional"),
            linkRow("Código fuente entregado (paquete)", "Incluido junto con este informe — repo git local con 19 commits, incluye validación contra el PDF real de la DNRPA"),
          ],
        }),
        new Paragraph({ text: "", spacing: { after: 200 } }),
        p("Nota: el sistema fue construido y validado end-to-end en un entorno de desarrollo (ver Sección 4 — Evidencia de funcionamiento, con capturas reales y log de sesión completo). Los links de GitHub y Render quedan pendientes de completar al momento de la publicación final.", { italics: true, size: 19, color: "9A3412" }),
      ],
    },

    // ============ SECCION 1 ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Sección 1 — Presentación del equipo y del proyecto"),
        h2("Integrantes"),
        bullet("Jorge Castillo — desarrollo full-stack: arquitectura del sistema, backend (FastAPI + SQLite), los 5 agentes especializados, frontend (chatbot + panel administrativo), diagramas de arquitectura y UML, evidencia de funcionamiento."),
        h2("Nombre del proyecto"),
        p("AutoValúa AI"),
        h2("Problema que resuelve"),
        p("La DNRPA publica mensualmente la tabla oficial de valuaciones de automotores y motovehículos en un PDF de aproximadamente 212 páginas, con filas de ancho fijo agrupadas por marca. Consultar el valor de un vehículo, o compararlo contra vigencias anteriores, requiere hoy abrir ese PDF manualmente y buscar fila por fila — y no existe ninguna vía estructurada para que un sistema de terceros (una aseguradora, una gestoría, un tasador) consulte ese dato de forma programática."),
        p("AutoValúa AI resuelve esa fricción con un sistema agéntico que ingiere automáticamente cada tabla mensual, la interpreta y la expone por dos canales: un chatbot conversacional en lenguaje natural y una API REST autenticada para integraciones externas."),
        h2("Público objetivo"),
        bullet("Particulares que necesitan saber el valor de su vehículo, vía el chatbot público."),
        bullet("Gestores de trámites registrales, que hoy pierden tiempo buscando manualmente en el PDF oficial."),
        bullet("Aseguradoras liquidando siniestros y tasadores, vía la API REST autenticada — el caso de uso que más se beneficia de un canal programático estandarizado."),
      ],
    },

    // ============ SECCION 2 ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Sección 2 — Arquitectura técnica"),
        p("El sistema se organiza como 6 agentes especializados (Scraper, Ingestor, Validador, Consulta/Matching, Analista Histórico, Notificador) coordinados por un orquestador central, siguiendo el ciclo Observar → Analizar → Planificar → Actuar → Evaluar → Aprender. De estos, 5 están implementados y probados en este prototipo (el Notificador tiene su modelo de datos y endpoint de configuración implementados, pero el disparo automático de alertas queda fuera del alcance de esta entrega)."),

        h2("Diagrama de arquitectura general"),
        p("Muestra cómo fluyen los datos desde la fuente (DNRPA) hasta los dos canales de exposición, qué componentes son IA (azul) versus lógica tradicional (gris), y dónde vive cada capa de la memoria persistente.", { size: 20, color: "64748B" }),
        image("01_arquitectura_general.png"),
        caption("Figura 1 — Arquitectura general: ingesta, memoria persistente, agentes de consulta y canales de exposición."),

        h2("Diagrama de flujo de agentes"),
        p("El ciclo de decisión de una consulta puntual: qué decide cada etapa, y en particular el punto que la devolución de medio ciclo señaló como poco especificado — el umbral de confianza y el cambio de estrategia — ahora está resuelto de forma explícita.", { size: 20, color: "64748B" }),
        image("02_flujo_agentes.png"),
        caption("Figura 2 — Ciclo de decisión: cambio de estrategia, escalado a humano y aprendizaje procedimental."),

        h2("UML — Diagrama de secuencia"),
        p("Cómo fluye una interacción completa, de punta a punta: una consulta ambigua que no resuelve con dos estrategias distintas, se escala a un humano, se resuelve, y la misma consulta repetida ya resuelve automático por el alias aprendido.", { size: 20, color: "64748B" }),
        image("03_secuencia_uml.png"),
        caption("Figura 3 — Secuencia completa: consulta ambigua, escalado, resolución humana y aprendizaje aplicado a la siguiente consulta."),

        h2("Validación contra el PDF real de la DNRPA"),
        p("Además del catálogo de muestra, el sistema fue probado contra el archivo oficial real de la DNRPA (vigencia 01/08/2026, 217 páginas, sin modificar). Esto responde directamente al punto más señalado en la devolución de medio ciclo: \"es una propuesta de diseño sin prototipo ni validación empírica\"."),
        p("Parsear el archivo real (formato Excel-export) requirió resolver a nivel de carácter — no de palabra pre-tokenizada — tres defectos de layout reales que no aparecían en los datos de muestra:"),
        bullet("Columnas de precio adyacentes pegadas sin espacio (ej. el valor 0km y el del año más reciente, cuando ambos son largos: \"10853271092235000\" son en realidad dos valores distintos)."),
        bullet("Texto de modelo muy largo que se superpone físicamente con la columna de carrocería en el PDF fuente — un defecto real del archivo oficial, no del parser."),
        bullet("Códigos de fila que no son 8 dígitos puros (motos con prefijo de letra como \"Q4910016\", o códigos de 7 dígitos), que inicialmente hacían perder ~40% de las filas al fusionarse con la fila anterior."),
        p("Resultado: 18.180 vehículos ingeridos correctamente. El 97% se parseó automáticamente; el 3% restante (548 filas, mayormente categorías raras como cuatriciclos o motocross fuera del vocabulario de carrocerías conocido) quedó escalado al panel administrativo con el texto sin interpretar — la misma regla de diseño aplicada de punta a punta: ante una ambigüedad de formato, el sistema deriva a un humano en vez de adivinar.", { bold: false }),
        image("08_consulta_dato_real_dnrpa.png", 480),
        caption('Consulta real contra el catálogo oficial: "AUDI A4 3.0 QUATTRO", valor $14.157.000 correspondiente al año 2007 (última vigencia con datos para ese modelo en la tabla real).'),
        image("10_panel_admin_datos_reales.png", 500),
        caption("Panel administrativo mostrando el catálogo real de 18.180 vehículos y los casos escalados por el Ingestor, cada uno con el código, el motivo y el texto original sin interpretar."),
      ],
    },

    // ============ SECCION 3 ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Sección 3 — Stack tecnológico"),
        table(
          ["Componente", "Tecnología / Herramienta", "Por qué se eligió esta y no otra"],
          [
            ["Backend", "Python 3.12 + FastAPI", "Tipado, async nativo, documentación OpenAPI automática — ideal para exponer el segundo canal (API REST) sin código adicional."],
            ["Matching difuso", "rapidfuzz (token_set_ratio)", "Implementación en C++, más rápida que fuzzywuzzy; token_set_ratio evitó el falso-positivo de WRatio en queries genéricas (documentado en agente_matching.py)."],
            ["Base de datos", "SQLite", "Prototipo de un solo nodo, cero configuración externa, suficiente para el volumen de esta entrega; el esquema (4 capas de memoria) es portable a Postgres si el proyecto escala."],
            ["Frontend", "HTML + JS vanilla", "Sin build step, servido directo por FastAPI (StaticFiles) — alcanza para demostrar el flujo completo sin la complejidad de un framework SPA."],
            ["Autenticación API", "Header X-API-Key vía variable de entorno", "Suficiente para el caso de uso (integraciones B2B conocidas), sin la complejidad de OAuth para un prototipo académico; las keys nunca quedan hardcodeadas en el código (ver Sección 6)."],
            ["Despliegue", "Render (free tier)", "Deploy directo desde GitHub, sin tarjeta de crédito, apto para un prototipo académico."],
          ],
          [1700, 2800, 4500],
        ),
      ],
    },

    // ============ SECCION 4 ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Sección 4 — Evidencia de funcionamiento"),
        p("Todas las capturas de esta sección corresponden a una sesión real del sistema corriendo (no mockups): se ingirieron las dos vigencias de muestra, el Validador detectó la anomalía de precio inyectada, y se ejecutaron consultas reales contra el catálogo. El log completo de esa sesión (13 pasos, con timestamps y respuestas JSON íntegras) está en el Anexo A."),

        h2("Pantalla principal — chatbot"),
        image("01_home_chatbot.png", 480),
        caption("El chatbot público, con sugerencias de consulta y aviso legal visible."),

        h2("Flujo de uso — consulta con match automático"),
        image("02_consulta_match.png", 480),
        caption('Consulta "toyota hilux srx 4x4 2024" → coincidencia exacta, confianza 100%.'),

        h2("Flujo de uso — fuzzy matching con error de tipeo"),
        image("03_consulta_fuzzy_output.png", 480),
        caption('Consulta "corola xei 2021" (typo real) → match por segunda estrategia (fuzzy solo-modelo), confianza 80%. El badge amarillo comunica que no fue un match perfecto.'),

        h2("Resultado de la IA — consulta ambigua escalada a humano"),
        image("04_consulta_escalada.png", 480),
        caption('Consulta genérica "auto 1.6 5 puertas" → ninguna estrategia superó el umbral de 80; el sistema muestra los 3 candidatos evaluados y sus scores, y deriva el caso al equipo humano en vez de adivinar.'),

        h2("Regla anti-alucinación en acción"),
        image("05_no_encontrado.png", 480),
        caption('Consulta "lamborghini aventador 2024" (vehículo inexistente en el catálogo) → el sistema responde "no encontrado" en vez de estimar un valor.'),

        h2("Panel administrativo — casos escalados y ciclo de ingesta"),
        image("06_panel_admin_casos.png", 500),
        caption("Panel con estadísticas en vivo, el ciclo de ingesta (Scraper simulado + Ingestor + Validador), y los dos casos escalados pendientes: uno de ambigüedad de consulta (con candidatos y campo para asignar alias) y uno de anomalía de precio detectada por el Validador (con el detalle estadístico: z-score, variación %, media de mercado)."),

        h2("Aprendizaje procedimental verificado"),
        image("07_alias_aprendido.png", 500),
        caption('Tras resolver el caso de ambigüedad asignando el alias "AUTO 1.6 5 PUERTAS" → código 80001, el contador de "Alias aprendidos" pasa a 1 y el caso desaparece de pendientes. El log de sesión (Anexo A, paso 9) confirma que repetir exactamente la misma consulta ambigua ahora resuelve automático con confianza 100% y estrategia "alias_aprendido" — cerrando el ciclo de aprendizaje de punta a punta.'),
      ],
    },

    // ============ SECCION 5 ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Sección 5 — Evaluación UX/UI"),
        h2("5.1 Heurísticas de Nielsen aplicadas al proyecto"),
        table(
          ["Heurística", "Cumple", "Evidencia / observación"],
          [
            ["Visibilidad del estado del sistema", "Sí", 'El chat muestra "Consultando la tabla oficial..." mientras espera, y cada resultado exhibe un badge de confianza (verde ≥95%, amarillo 80-94%).'],
            ["Coincidencia con el mundo real", "Parcial", "Usa el vocabulario oficial de la DNRPA (vigencia, código MTM/FMM), útil para gestorías pero menos transparente para un particular sin ese contexto."],
            ["Control y libertad del usuario", "Parcial", "Se puede reformular la consulta libremente, pero no hay forma de cancelar una consulta ya escalada desde el chat."],
            ["Consistencia y estándares", "Sí", "Los tres estados de respuesta (match / escalado / no encontrado) usan siempre el mismo layout y los mismos colores semánticos en todo el sistema."],
            ["Prevención de errores", "Sí", "La regla anti-alucinación evita el error más costoso del dominio: nunca se muestra un valor inventado."],
            ["Reconocimiento antes que recuerdo", "Sí", "Los botones de sugerencia muestran ejemplos de consulta sin que el usuario tenga que recordar el formato."],
            ["Flexibilidad y eficiencia de uso", "Parcial", "Acepta lenguaje libre con errores de tipeo, pero no hay atajos para usuarios frecuentes (favoritos, historial visible)."],
            ["Diseño estético y minimalista", "Sí", "Cada resultado muestra solo lo esencial: vehículo, valor, vigencia, confianza y nota legal."],
            ["Ayuda a reconocer y solucionar errores", "Sí", "Ante una consulta ambigua, el sistema muestra los candidatos concretos y sus scores, no solo un genérico \"no entendí\"."],
            ["Ayuda y documentación", "No", "No hay una sección de ayuda dentro del chat más allá del mensaje de bienvenida — es la heurística más débil del diseño actual."],
          ],
          [3200, 1200, 4600],
        ),
        new Paragraph({ text: "", spacing: { after: 160 } }),
        p("Resultado: 6 de 10 heurísticas se cumplen completamente, 3 parcialmente y 1 no se cumple.", { italics: true, size: 20, color: "64748B" }),

        h2("5.2 Evaluación orientada al público objetivo"),
        p("El sistema separa deliberadamente dos públicos con necesidades distintas: el particular (chatbot, sin conocimiento técnico) y el integrador técnico (API REST, con JSON y headers). Ninguno de los dos ve la interfaz pensada para el otro — el particular nunca ve un código MTM crudo salvo que la consulta lo requiera, y la aseguradora recibe exactamente ese dato estructurado en la respuesta de la API."),
        p('El lenguaje técnico ("fuzzy search", "z-score") se mantiene fuera del chatbot público y solo aparece en el panel administrativo, que es para el equipo interno.'),
        p("No se realizó una prueba de usabilidad formal con un usuario ajeno al proyecto en esta entrega — es una limitación real, no un dato a maquillar. La evidencia de la Sección 4 demuestra funcionamiento técnico de punta a punta, pero no reemplaza una validación externa. Queda como trabajo futuro antes de cualquier uso productivo.", { italics: true }),
      ],
    },

    // ============ SECCION 6 ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Sección 6 — Evaluación de ciberseguridad"),
        p("Log de consideraciones de seguridad pensadas activamente durante el desarrollo:"),
        table(
          ["Riesgo identificado", "Tipo", "Medida implementada o decisión tomada"],
          [
            ["Inyección de prompt / manipulación de la consulta", "Prompt injection", "El matching es determinístico (regex + fuzzy matching), no un LLM libre interpretando texto — el input del usuario nunca se concatena a un prompt de sistema ni se ejecuta como código."],
            ["Exposición de API keys", "Secretos en código", "Corregido durante esta entrega: las keys ya no están hardcodeadas — se leen de la variable de entorno AUTOVALUA_API_KEYS, con .env en .gitignore y .env.example documentando el formato sin exponer valores reales."],
            ["Datos de usuarios almacenados", "Privacidad", "La memoria episódica guarda el texto de la consulta y un identificador de usuario, sin datos de pago ni ubicación. Limitación reconocida: falta una política de retención/expiración de ese log."],
            ["Acceso no autorizado a la API REST", "Autenticación", "Todo endpoint bajo /api/v1/* exige el header X-API-Key; sin key válida responde 401 (verificado en el log de sesión, Anexo A, paso 12). El canal /chat/* es intencionalmente público."],
            ["Inyección SQL", "Inyección de datos", "Todas las queries a SQLite usan parámetros (?) vía el driver estándar, nunca concatenación de texto del usuario dentro del SQL."],
            ["Denegación de servicio por consultas costosas", "Disponibilidad", "El fuzzy matching recorre el catálogo completo en cada consulta; con la tabla real (miles de filas) esto podría degradar el tiempo de respuesta bajo alta concurrencia. No se implementó rate-limiting ni caché — riesgo abierto para producción."],
          ],
          [2600, 1600, 4800],
        ),
        new Paragraph({ text: "", spacing: { after: 160 } }),
        p("Mínimo de 4 filas cumplido (6 documentadas), incluyendo una corrección de seguridad real aplicada durante el desarrollo de esta entrega — no solo declarada en la tabla.", { italics: true, size: 20, color: "64748B" }),
      ],
    },

    // ============ PARTE 2 ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Parte 2 — IA local en el proyecto"),

        h2("1. ¿Qué papel jugaría un LLM/SLM local?"),
        p("AutoValúa AI deliberadamente no depende de un LLM para su función crítica: el matching es determinístico (rapidfuzz + reglas), justamente para poder garantizar la regla anti-alucinación de forma auditable. Un LLM/SLM local no reemplazaría ese componente — lo haría menos verificable, no más confiable, en un dominio con valor legal/administrativo."),
        p("Donde sí tendría un rol real es como componente de soporte, nunca como agente de decisión:"),
        bullet("Interpretación de consultas más ambiguas o mal escritas que un typo simple, sin depender de una API externa por cada mensaje del chat."),
        bullet("Redacción más natural del mensaje de escalado — el LLM redactaría la explicación, pero los datos (candidatos, scores) los seguiría generando el motor determinístico."),

        h2("2. ¿Qué le aportaría al usuario de la aplicación?"),
        bullet("Privacidad: procesar la interpretación del texto localmente reduce la exposición de información patrimonial (qué vehículo tiene una persona) a una API externa de terceros."),
        bullet("Costo: con volumen alto (aseguradoras, gestorías), pagar por token externo por cada mensaje escala mal — un modelo local no tiene costo marginal por consulta."),
        bullet("Velocidad: para interpretar una frase corta, un SLM local evita la latencia de red hacia una API externa."),
        p("No cambiaría qué puede pedirle el usuario al sistema — la regla anti-alucinación seguiría vigente sin importar qué componente interpreta el texto."),

        h2("3. ¿Qué le aportaría al equipo como profesional?"),
        p("Tener el modelo corriendo localmente permitiría analizar patrones en las consultas que hoy quedan en la memoria episódica sin mandar ese dataset a ningún tercero — por ejemplo, qué modelos se consultan con más frecuencia sin encontrar match, información que hoy ya se prioriza para revisión humana pero que un análisis más profundo con el modelo local podría convertir en sugerencias automáticas de nuevos alias, sin exponer ese log de comportamiento a una API externa."),

        h2("4. ¿Qué limitaciones concretas tiene versus una API en la nube?"),
        bullet("Capacidad de hardware: un SLM (Phi-3 Mini, Gemma 2B) corre razonablemente en CPU, pero su calidad de interpretación de lenguaje libre es notablemente inferior a un modelo de frontera vía API."),
        bullet("Calidad para el caso de uso específico: el dominio (nombres de modelos de autos argentinos, jerga coloquial) es un long tail que un modelo pequeño genérico no necesariamente maneja mejor que las reglas + fuzzy matching ya implementadas — habría que evaluarlo empíricamente antes de justificar la complejidad operativa."),
        bullet("Mantenimiento: correr y actualizar un modelo local es responsabilidad propia (versionado, parches, monitoreo de recursos), carga que con una API externa asume el proveedor."),

        h2("Entregable opcional — Ollama"),
        p("Queda pendiente de ejecutar en el entorno local del equipo (correr un modelo con Ollama y capturar la respuesta a una pregunta del proyecto) antes de la entrega, si se quiere sumar ese punto extra.", { italics: true }),
      ],
    },

    // ============ ANEXO A ============
    {
      properties: { page: PAGE },
      headers: { default: HEADER }, footers: { default: FOOTER },
      children: [
        h1("Anexo A — Log de sesión real completo"),
        p("13 pasos documentados con timestamps: ingesta de ambas vigencias (con detección real de la anomalía inyectada), los 4 tipos de resultado de consulta (match exacto, fuzzy, escalado, no-encontrado), resolución humana de un caso y verificación de que el aprendizaje funciona, consulta al histórico, y prueba de la API REST autenticada con y sin key. También disponible en capturas/log_sesion_real.txt."),
        ...fs.readFileSync(path.join(__dirname, "..", "capturas", "log_sesion_real.txt"), "utf-8")
          .split("\n")
          .map((line) => new Paragraph({
            children: [new TextRun({ text: line.length ? line : " ", font: "Consolas", size: 15, color: "334155" })],
            spacing: { after: 0 },
          })),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(path.join(__dirname, "AutoValua_AI_Entrega_Final.docx"), buf);
  console.log("Documento generado.");
});
