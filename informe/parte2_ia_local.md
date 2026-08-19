# PARTE 2 — IA local en el proyecto

*(Borrador de partida — ajustar con tu propia mirada antes de entregar, especialmente las preguntas 2 y 3, que piden tu perspectiva personal)*

## 1. ¿Qué papel jugaría un LLM/SLM local en el proyecto?

AutoValúa AI, tal como está construido en este prototipo, deliberadamente **no depende de un LLM para su función crítica**: el matching de vehículos es determinístico (rapidfuzz + reglas), justamente para poder garantizar la regla anti-alucinación de forma verificable. Un LLM/SLM local no reemplazaría ese componente — lo haría menos auditable, no más confiable, en un dominio con valor legal/administrativo.

Donde sí tendría un rol real es como **componente de soporte**, no como agente principal:

- **Interpretación de consultas más ambiguas o mal escritas**: hoy el parser de la consulta es regex + stopwords (ver `agente_matching.py`). Un SLM local (ej. Phi-3 Mini) podría mejorar la extracción de marca/modelo/año en consultas más naturales o con errores más severos que un typo simple, sin depender de una API externa por cada mensaje del chat.
- **Generación de la explicación al usuario en el caso ambiguo**: actualmente el mensaje de escalado es una plantilla fija con la lista de candidatos. Un SLM local podría redactar una explicación más natural de por qué el sistema no pudo decidir, mantiendo los datos (candidatos, scores) generados por el motor determinístico — el LLM redacta, no decide.

Sería entonces un **subagente de soporte** (capa de lenguaje), nunca el agente principal de decisión.

## 2. ¿Qué le aportaría al usuario de la aplicación?

- **Privacidad**: las consultas de valuación pueden revelar qué vehículo tiene una persona, lo cual es información patrimonial. Procesar la interpretación del texto localmente (sin mandarlo a una API externa de terceros) reduce la superficie de exposición de esos datos.
- **Costo**: con volumen alto de consultas (pensado como servicio para aseguradoras/gestorías), pagar por token a una API externa por cada mensaje del chat escala mal. Un modelo local no tiene costo marginal por consulta.
- **Velocidad**: para el caso de uso puntual (interpretar una frase corta), un SLM local corriendo en la misma infraestructura evita la latencia de red hacia una API externa.

No cambiaría *qué* puede pedirle el usuario al sistema (la regla anti-alucinación seguiría vigente sin importar qué componente interpreta el texto), pero sí podría mejorar la tolerancia a consultas mal formuladas.

## 3. ¿Qué te aportaría a vos como profesional?

*(Completar con tu propia reflexión — un punto de partida:)*

Tener el modelo corriendo localmente permitiría analizar patrones en las consultas que hoy quedan en la memoria episódica (`consultas_log`) sin mandar ese dataset a ningún tercero — por ejemplo, qué modelos se consultan con más frecuencia sin encontrar match, lo cual hoy ya se prioriza para revisión humana (Sección 7 del diseño original) pero que un análisis más profundo con el modelo local podría convertir en sugerencias automáticas de nuevos alias, sin exponer ese log de comportamiento de usuarios a una API externa.

## 4. ¿Qué limitaciones concretas tiene versus una API en la nube?

- **Capacidad de hardware**: un SLM como Phi-3 Mini o Gemma 2B corre razonablemente en CPU, pero la calidad de interpretación de lenguaje natural libre es notablemente inferior a un modelo de frontera vía API — para este caso de uso (frases cortas, dominio acotado) es un trade-off aceptable, pero no lo sería para un chatbot de propósito general.
- **Calidad para el caso de uso específico**: el dominio (nombres de modelos de autos argentinos, jerga coloquial) es un long tail que un modelo pequeño genérico no necesariamente maneja mejor que las reglas + fuzzy matching ya implementadas — habría que evaluar empíricamente si de verdad mejora sobre la solución actual antes de justificar la complejidad operativa de mantener un modelo corriendo.
- **Mantenimiento**: correr y actualizar un modelo local es responsabilidad propia (versionado, parches, monitoreo de recursos) — con una API externa esa carga la asume el proveedor.

## Entregable opcional — Ollama

Ver `capturas/log_sesion_real.txt` para el log de sesión del sistema determinístico. Para el entregable opcional de Ollama (correr un modelo local y mostrar una captura respondiendo una pregunta del proyecto), se necesita instalar Ollama en la máquina del equipo — no está disponible en este entorno de ejecución, así que queda pendiente de correr localmente antes de la entrega si se quiere sumar ese punto extra.
