# Especificacion de implementacion: recepcion y enrutamiento de RFPs

## Objetivo

Implementar la Parte 1 del flujo agéntico de RFPs de Nexova. Ventas debe poder cargar un PDF, consultar el estado de su ticket y ver, sin volver a leer el original, qué necesita cada departamento activo y a quién debe pedírselo. Esta fase termina con un handoff persistido para la Parte 2; no genera propuestas ni borradores.

## Fuentes de verdad

- Departamentos, responsables, formato de RFP, ejemplos y reglas de negocio: [`docs/briefing-rft-intake.md`](../docs/briefing-rft-intake.md). Este es el `briefing-rft-intake.md` adjunto como referencia de `company-BRIEFING.md`; no se encontró una copia en `data/`.
- Contratos HTTP, autenticación y persistencia: reutilizar los existentes en `services/`; no crear un segundo servidor HTTP ni sustituir PostgreSQL/Supabase por TinyDB o JSON.

## Reglas globales

- Mantener el código HTTP bajo `services/`. Los routers aceptan/validan solicitudes, consultan el estado y disparan el procesamiento; la lógica del pipeline pertenece a `data/pipelines/rfp_intake/`.
- Crear un grafo `rfp_intake` dedicado, con nodos/agentes identificables para conversión, clasificación, extracción, orquestación, workers y síntesis. No conectar nodos RFP al grafo CX/knowledge-agent.
- Los scripts de reproceso o smoke test, si hacen falta, van en `scripts/`; no deben servir como otro API.
- Persistir en PostgreSQL (Supabase), usando SQLModel o la capa existente, el ticket, metadatos, secciones por departamento y handoff. Los PDFs y Markdown son artefactos de proceso, no fuentes de verdad para esas entidades.
- Ningún agente puede inventar volúmenes, presupuesto, fechas, SLA solicitados u otros datos ausentes. Registrar la ausencia como pregunta abierta o dato no especificado.
- No activar todos los departamentos por defecto. Solo crear secciones y tareas de los departamentos requeridos por los servicios detectados.
- Mantener el estado del ticket consistente con el trabajo real. Un rechazo de clasificación es `descartado`; una ejecución válida terminada es `analisis_completo`. Un fallo técnico no es un rechazo de negocio ni debe dejar un ticket eternamente en `analizando`: conservar el error de forma trazable y permitir reintento según el mecanismo existente, sin inventar un estado público incompatible.
- No almacenar secretos ni incluir el contenido completo del PDF o Markdown en logs.

## Contrato funcional y persistencia

### Recepción y consulta

- La interfaz de `uis/backoffice` permite cargar únicamente PDF y crea un ticket por documento.
- Guardar el PDF recibido bajo `data/raw/` con un nombre seguro y no colisionante; persistir su ruta en el ticket. No tratar los PDFs de ejemplo como datos ya sembrados.
- El endpoint de carga valida tipo/tamaño y persistencia inicial, crea el ticket en `analizando`, agenda el pipeline asíncrono y responde sin esperar al análisis.
- Proveer mediante el backend existente consulta de estado y resultado por `ticket_id`. La UI refresca o consulta el estado hasta `analisis_completo` o `descartado`, y muestra el resultado, los errores recuperables y el estado de carga claramente.
- Restringir la carga y consulta con el mecanismo de autenticación/autorización existente. No exponer rutas del sistema de archivos ni aceptar una ruta local suministrada por el cliente.

### Entidades mínimas

- **Ticket**: `ticket_id`, `rfp_id`, `status`, `raw_pdf_path`, `created_at`, `updated_at`; añadir solo campos de error/reintento que encajen con la capa de persistencia existente.
- **RFP metadata**: `client_name`, `client_hq` (España/Miami, o no especificado), `services_requested`, `scope`, `deadline`, `budget_range`, `departments_needed` y métricas de legibilidad. Incluir preguntas abiertas para datos relevantes ausentes. Relacionar de forma persistente con el ticket/RFP.
- **DepartmentSection**: `ticket_id`, `department_id`, `key_aspects`; conservar compatibilidad con los campos previstos para etapas futuras (`draft_content`, evaluaciones y aprobación) sin implementarlas en esta fase.
- **Handoff**: persistir `ticket_id` junto con el payload estructurado del synthesizer (`key_aspects` y workstreams/departamentos activos) y un indicador o estado que permita a la Parte 2 consumirlo sin volver a parsear el PDF. No se requiere un segundo API.

Las escrituras relacionadas con el resultado final deben ser transaccionales cuando sea posible: no marcar el ticket `analisis_completo` antes de guardar metadatos, secciones y handoff. Un documento descartado debe conservar el ticket y el motivo del rechazo.

## Flujo del pipeline

### 1. PDF a Markdown

- Convertir el PDF a Markdown en cuanto se acepta la recepción y antes de invocar cualquier agente. Usar MarkItDown; si el entorno obliga a una alternativa, documentar la herramienta, su configuración y por qué mantiene el requisito de conversión previa.
- Guardar el Markdown como artefacto derivado bajo una ubicación de proceso apropiada; no reemplaza ni modifica el PDF original.
- Si la conversión falla o no produce texto utilizable, registrar un fallo técnico claro y detener ese ticket sin clasificarlo silenciosamente como no-RFP.

### 2. Clasificación

- El clasificador recibe el Markdown, no el PDF binario. Devuelve una decisión estructurada de RFP válida/no válida, motivo y evidencia breve del documento.
- Aceptar tanto RFPs formales como solicitudes informales por correo cuando pidan a Nexova una propuesta de servicios. Rechazar pitches entrantes de proveedores u otros documentos que no sean solicitudes de propuesta de un cliente.
- Si no es válida, guardar motivo y evidencia, cambiar el ticket a `descartado` y terminar ese flujo sin afectar otros tickets.
- Ante evidencia ambigua, no ocultar la decisión: incluir motivo/evidencia para facilitar revisión y mantener el comportamiento conforme al contrato de estados definido por el producto.

### 3. Extracción de metadatos y legibilidad

- Solo tras clasificar como RFP válida, extraer del Markdown cliente, sede, servicio(s), alcance/volumen, fecha límite, presupuesto de referencia, departamentos aplicables y preguntas abiertas.
- Determinar la moneda como dato derivado de la sede cuando esta sea conocida: España → EUR; Miami/EE. UU. → USD. No inferir la sede a partir de la moneda ni inventarla cuando falte evidencia.
- Calcular y persistir métricas de legibilidad sobre el texto convertido (se recomienda `py-readability-metrics`) que ayuden a anticipar costo de procesamiento. Registrar también unidad/idioma y cualquier limitación de cálculo; no presentar la métrica como costo monetario exacto.
- Los valores extraídos deben conservar su fuente o evidencia suficiente para revisión y distinguir datos ausentes de valores cero/vacíos.

### 4. Orquestador y workers

- El orquestador identifica servicios y activa departamentos usando exclusivamente estos IDs y responsables del briefing:

| `department_id` | Servicio que lo activa | Responsable |
| --- | --- | --- |
| `seleccion` | Headhunting/búsqueda y roles a cubrir | Javier Almeida |
| `capacitacion` | Formación o capacitación corporativa | Elena Vargas |
| `soporte` | Outsourcing de soporte al cliente | Roberto Díaz |

- Una solicitud de búsqueda ejecutiva y formación activa `seleccion` y `capacitacion`; una petición de soporte outsourced activa `soporte`. `seleccion` puede activarse además para soporte solo si el documento pide explícitamente reclutamiento/selección de esos agentes. La mención de varios servicios activa únicamente los departamentos correspondientes.
- Si el texto menciona un equipo/servicio que no corresponde claramente a un ID conocido, no crear departamentos arbitrarios ni mapearlo por defecto a los tres. Dejarlo como pregunta abierta para Ventas y limitar el trabajo a los departamentos respaldados por evidencia.
- Cada worker recibe metadatos compartidos y solo los extractos relevantes a su departamento, nunca requiere el PDF binario. Cada uno produce `key_aspects` estructurados, hechos con evidencia y preguntas abiertas.
- Orientar los aspectos a lo que cada departamento debe aportar: `seleccion` (roles, tiempo estimado de cierre y horas de consultoría), `capacitacion` (programas aplicables, duración y modalidad), `soporte` (dotación, turnos y SLA solicitado). Las estimaciones internas no deben presentarse como cifras pedidas por el cliente.
- Registrar explícitamente cifras requeridas que falten; nunca completar el número de roles, agentes o participantes por plausibilidad.
- Ejecutar workers independientes en paralelo cuando el runtime del grafo lo permita. Si trabajadores producen afirmaciones incompatibles, el synthesizer debe conservar las evidencias, marcar la contradicción y convertirla en pregunta abierta; no resolverla inventando consenso.

### 5. Synthesizer y handoff

- El synthesizer consolida los resultados sin añadir hechos nuevos y genera un resumen accionable para Marcos Ibáñez, Sales Director: departamentos activos, aspectos clave, datos faltantes/preguntas abiertas y responsable a contactar.
- Incluir contacto por departamento según el briefing: Javier Almeida (`seleccion`), Elena Vargas (`capacitacion`) y Roberto Díaz (`soporte`). No listar como asignados departamentos que no fueron activados.
- Persistir el resumen y el payload de handoff junto con las secciones. Tras confirmar la persistencia, marcar el ticket `analisis_completo`.
- El handoff de Parte 2 debe contener como mínimo `ticket_id`, metadatos normalizados, departamentos/workstreams activos y `key_aspects` por departamento. Su contrato debe documentarse y permitir continuar sin releer ni reparsear el PDF.
- Esta fase no genera precios, propuestas, borradores por departamento, evaluaciones, aprobaciones ni documento final. Las reglas de propuesta del briefing (garantía a 90 días, cierre mínimo de 15 días hábiles, SLA de 24 horas y anonimización de referencias) quedan para fases posteriores.

## Casos de aceptación de negocio

Validar mediante carga por la UI usando los PDFs indicados por el briefing, si están disponibles en el entorno:

- `nexova-request-1.pdf`: aceptar Vantex Retail Group (Madrid); extraer búsqueda de 5 mandos medios y programa trimestral de liderazgo; activar `seleccion` y `capacitacion`; moneda EUR; guardar preguntas abiertas si falta algún dato.
- `nexova-request-2.pdf`: aceptar la solicitud informal de NubeSoft (SaaS Miami) para soporte 24/7 de 12 agentes; activar `soporte`. Activar `seleccion` solo si el documento pide explícitamente ese servicio. Moneda USD.
- `nexova-request-3.pdf`: rechazar el pitch de proveedor ATS como no-RFP; persistir el ticket en `descartado` con motivo.

Ubicación esperada por el briefing: `rfp-requests/nexova/`. Si los archivos no están disponibles, no fabricar fixtures que pretendan verificarlos; informar esa limitación y cubrir el contrato con pruebas unitarias.

## Pruebas y criterios de salida

- Añadir pruebas unitarias en `tests/pipelines/` para decisiones del clasificador (formal e informal aceptadas, pitch de proveedor rechazado) y al menos un worker (departamento correcto, extracto relevante, ausencia de invención ante cifras faltantes).
- Las pruebas no deben depender de PostgreSQL remoto, servicios externos ni un LLM en vivo: simular conversión/clasificador/modelos según el límite probado y comprobar entradas/salidas estructuradas.
- Verificar persistencia PostgreSQL de ticket, metadata, secciones y handoff; probar que la carga responde antes de terminar el pipeline y que el estado consultado refleja su progreso y resultado.
- Verificar que el clasificador consume Markdown y que ningún agente se invoca antes de completar la conversión.
- Verificar que un rechazo no afecta otros tickets, que los workers activados coinciden con los servicios, y que metadatos/resultados mantienen los valores ausentes como preguntas abiertas.
- Criterio final: los dos ejemplos válidos llegan a `analisis_completo` con contactos y aspectos por departamento; el pitch llega a `descartado`; todos los datos de negocio requeridos y el handoff quedan en PostgreSQL; la Parte 2 puede iniciar desde el handoff sin releer el original.

## Preguntas de diseño que deben quedar resueltas en la implementación

- ¿Qué contrato de background task existente se reutiliza y cómo se reintenta una ejecución interrumpida sin duplicar entidades?
- ¿Cómo se identifica de forma estable el ticket/RFP y se evita sobrescribir archivos o duplicar el procesamiento al reintentar?
- ¿Qué esquema exacto versionado tendrá el handoff y cómo lo consumirá la Parte 2?
- ¿Qué campos de evidencia conserva cada extracción para distinguir un dato explícito, uno derivado de una regla y uno ausente?