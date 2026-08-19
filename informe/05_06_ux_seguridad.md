# Sección 5 — Evaluación UX/UI

## 5.1 Heurísticas de Nielsen aplicadas al proyecto

| Heurística | Cumple | Evidencia / observación |
|---|---|---|
| Visibilidad del estado del sistema | Sí | El chatbot muestra "Consultando la tabla oficial..." mientras espera la respuesta del backend (ver captura 02), y cada resultado exhibe un badge de confianza (verde ≥95%, amarillo 80-94%) para que el usuario entienda qué tan seguro está el sistema de su propia respuesta — no es una caja negra que solo dice "sí" o "no". |
| Coincidencia con el mundo real | Parcial | El vocabulario (marca, modelo, vigencia, código MTM/FMM) es el mismo que usa la DNRPA, lo cual ayuda a un usuario de gestoría/aseguradora pero puede ser menos transparente para un particular sin conocimiento del dominio (ej. no explica qué es una "vigencia" la primera vez que aparece). |
| Control y libertad del usuario | Parcial | El usuario puede reformular la consulta libremente en cualquier momento, pero no hay forma de "deshacer" una consulta ambigua ya escalada ni de cancelar una notificación configurada desde el chat (solo desde el panel admin, que además no está pensado para el usuario final). |
| Consistencia y estándares | Sí | Los tres estados de respuesta (match/escalado/no encontrado) usan siempre el mismo layout de tarjeta y los mismos colores semánticos en todo el sistema (verde=éxito, amarillo=incertidumbre, rosa/rojo=requiere intervención humana), tanto en el chat como en el panel admin. |
| Prevención de errores | Sí | La regla anti-alucinación evita el error más costoso del dominio: nunca se muestra un valor inventado. Cuando el sistema no está seguro (score 60-79), no arriesga una respuesta automática — prefiere escalar. |
| Reconocimiento antes que recuerdo | Sí | Los botones de sugerencia ("corola 2021", "toyota hilux srx", etc.) le muestran al usuario ejemplos de qué puede preguntar, sin que tenga que recordar el formato exacto. |
| Flexibilidad y eficiencia de uso | Parcial | El chat acepta lenguaje natural libre (typos incluidos), lo cual es eficiente para el usuario nuevo. Pero no hay atajos para usuarios frecuentes (ej. favoritos, historial visible de sus propias consultas) — la memoria episódica existe en la base de datos pero todavía no se expone en la interfaz del usuario. |
| Diseño estético y minimalista | Sí | La interfaz del chat muestra solo lo esencial por resultado (vehículo, valor, vigencia, confianza, nota legal) sin ruido visual adicional. |
| Ayuda para reconocer, diagnosticar y solucionar errores | Sí | Cuando la consulta es ambigua, el sistema no dice solo "no entendí": muestra los candidatos concretos que evaluó y sus scores, dándole al usuario contexto real sobre por qué no pudo decidir solo. |
| Ayuda y documentación | No | No hay una sección de ayuda ni ejemplos adicionales dentro del chat más allá del mensaje de bienvenida y las 4 sugerencias iniciales. Es la heurística más débil del diseño actual. |

**Resultado**: 6 de 10 heurísticas se cumplen completamente, 3 parcialmente y 1 no se cumple — cubre el mínimo de 5 heurísticas evaluadas que pide la consigna, con honestidad sobre las que todavía no están resueltas.

## 5.2 Evaluación orientada al público objetivo

**¿El diseño es apropiado para el nivel técnico del usuario final?** El sistema tiene dos públicos con necesidades distintas: el particular (vía chatbot, sin conocimiento técnico) y el integrador técnico (vía API REST, con documentación de headers y JSON). Separar ambos canales — en vez de forzar a todos por una sola interfaz — es la decisión de UX más importante del proyecto: el particular nunca ve un JSON ni un código MTM crudo salvo que quiera profundizar, mientras que la aseguradora recibe exactamente eso en la respuesta de la API.

**¿El lenguaje visual y textual es comprensible para ese usuario?** Sí para el chatbot: se evitan términos técnicos como "fuzzy search" o "z-score" en la interfaz orientada al público (esos términos solo aparecen en el panel administrativo, que es para el equipo interno, donde sí es apropiado usarlos).

**¿Se hizo alguna prueba con un usuario real?** No se realizó una prueba de usabilidad formal en esta entrega — es una limitación real del trabajo, no un dato a maquillar. La evidencia de funcionamiento (Sección 4) demuestra que el sistema funciona técnicamente extremo a extremo, pero no reemplaza una validación con un usuario que no conozca el proyecto de antemano. Queda como trabajo futuro natural antes de cualquier uso productivo.

---

# Sección 6 — Evaluación de Ciberseguridad

## Log de consideraciones de seguridad

| Riesgo identificado | Tipo | Medida implementada o decisión tomada |
|---|---|---|
| Inyección de prompt / manipulación de la consulta | Prompt injection | El "NLP" de este prototipo es determinístico (regex + fuzzy matching, no un LLM libre interpretando la consulta), así que no hay superficie de prompt injection clásica en el agente de matching. El texto del usuario nunca se concatena a un prompt de sistema ni se ejecuta como código; solo se usa como input de comparación de strings. |
| Exposición de API keys | Secretos en código | Corregido durante esta entrega (ver commit "Seguridad: API keys movidas a variable de entorno"): las keys ya no están hardcodeadas — se leen de `AUTOVALUA_API_KEYS` vía variable de entorno, con `.env` en `.gitignore` y `.env.example` documentando el formato sin exponer valores reales. |
| Datos de usuarios almacenados | Privacidad | La memoria episódica (`consultas_log`) guarda el texto de la consulta y un identificador de usuario de texto libre, sin validar que no contenga datos personales sensibles (ej. si alguien escribe su DNI por error). No se almacena ningún dato de pago, ubicación ni contacto. Limitación reconocida: falta una política de retención/expiración de este log. |
| Acceso no autorizado a la API REST | Autenticación | Implementado: todo endpoint bajo `/api/v1/*` exige el header `X-API-Key` contra la lista cargada desde variable de entorno; sin key válida responde `401` (verificado en la Sección 4, paso 12 del log de sesión). El canal `/chat/*` es intencionalmente público, como define el diseño original. |
| Inyección SQL | Inyección de datos | Todas las queries a SQLite usan parámetros (`?`) vía el driver estándar de Python, nunca f-strings ni concatenación de texto del usuario dentro del SQL — se verificó especialmente en `agente_matching.py`, que es el punto que recibe texto libre del usuario. |
| Denegación de servicio por consultas costosas | Disponibilidad | El fuzzy matching recorre el catálogo completo de vigencia en cada consulta (`O(n)` sobre ~20 vehículos de muestra). Con la tabla real (~miles de filas) esto podría degradar el tiempo de respuesta bajo alta concurrencia; no se implementó rate-limiting ni caché en este prototipo — queda como riesgo abierto para producción. |

**Mínimo de 4 filas cumplido (6 filas documentadas)**, incluyendo una corrección de seguridad real aplicada durante el desarrollo de esta entrega, no solo declarada en la tabla.
