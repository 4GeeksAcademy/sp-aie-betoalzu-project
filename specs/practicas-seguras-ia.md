# Spec: auditoría y endurecimiento de prácticas seguras en IA — Nexova

## Objetivo

Auditar y endurecer los sistemas de IA construidos en el fork de Nexova antes de considerarlos aptos para producción. La entrega comprende tanto cambios de seguridad verificables como un informe formal: inventario completo, evaluación NIST, evaluación OWASP Top 10, pruebas reproducibles y plan priorizado de remediación.

Esta especificación **no presupone que los controles ya existan**. El trabajo debe inspeccionar la implementación actual, distinguir evidencia observada de recomendaciones y corregir las brechas críticas confirmadas dentro del alcance.

## Fuentes de requisitos

- Briefing de negocio y seguridad: [`docs/briefing-practicas-de-seguridad.md`](../docs/briefing-practicas-de-seguridad.md) (fuente normativa para sistemas, datos, jurisdicciones, casos de inyección, acciones irreversibles y alcance OWASP).
- Reto y criterios de aceptación: [`precticas-seguras.md`](../precticas-seguras.md).

## Alcance de la auditoría

Inspeccionar todo lo construido en el fork en las siguientes áreas, incluyendo rutas de datos, identidad, permisos, secretos, configuración, logging, pruebas y límites entre tenants/usuarios:

1. **Pipeline de selección asistida**: ingesta/extracción de CV, scoring y ranking.
2. **RAG de candidatos**: indexación, recuperación, filtrado de acceso y presentación de resultados.
3. **Agente de soporte de outsourcing**: recepción de tickets, memoria, tools/MCP, escalado y cierre.
4. **Agente de prospección comercial**: selección de datos, generación y envío de comunicaciones.
5. **Backend y API**, incluidos endpoints que disparan modelos, autenticación/autorización y proxies.
6. **Frontend y dashboards**: exposición de datos, sesiones, manejo de errores y controles de acciones.
7. **MCP, herramientas y workflows**: servidores, scopes, validación de argumentos y efectos secundarios.
8. **Infraestructura/operación**: configuración disponible de despliegue, SSH, usuario de ejecución, permisos y firewall.

Buscar otros agentes, RAG, workflows o integraciones de IA presentes en el repositorio; incorporarlos al inventario aunque no figuren en los cuatro sistemas de partida. Si un componente del briefing no aparece o no está desplegado en el fork, consignarlo como **no encontrado/no verificable**, con búsqueda y evidencia, no excluirlo silenciosamente.

## Propietarios y responsabilidad de terceros

Asignar a cada componente un responsable interno por **rol** (p. ej. CTO/Seguridad, responsable de Selección, responsable de Soporte, responsable Comercial, propietario de plataforma). No inventar nombres: indicar que el rol/nombre debe ser confirmado por Nexova cuando no haya evidencia en el repositorio. Separar siempre:

- **Accountable interno**: propietario del propósito, acceso, configuración, aprobación y respuesta ante incidentes.
- **Proveedor externo**: proveedor del modelo/herramienta/hosting, sus controles y límites contractuales conocidos.
- **Responsabilidad compartida y pendiente**: protección de datos, retención, región, subprocesadores, logging, incidentes y controles que deben verificarse en contrato o consola.

La utilización de un proveedor no transfiere la responsabilidad de Nexova sobre los datos, permisos, prompts, decisiones ni aprobación de acciones.

## Requisitos de implementación

### A. Secretos, datos y límites de confianza

- Buscar credenciales, API keys, tokens, contraseñas y claves privadas hardcodeadas en código, configuración, historial/artefactos rastreables y ejemplos. No imprimir valores secretos en el informe o logs.
- Eliminar el uso de credenciales hardcodeadas y leerlas de variables de entorno o un vault/secret manager. Añadir validación de configuración para fallar de forma segura cuando falte una credencial necesaria; excluir secretos de respuestas y trazas.
- Documentar clasificación y flujo de los datos sensibles identificados por el briefing: CVs, historial laboral, pretensiones salariales, información de empleados/clientes y contactos de prospectos. Aplicar minimización, control por rol/tenant y no usar datos personales reales en las pruebas/informe.
- Validar y limitar formato, tamaño y tipo de entradas antes de enviarlas a modelos o herramientas. Usar consultas/serialización seguras para cualquier salida que pudiera convertirse en SQL, código, URL o argumentos de herramienta; no ejecutar texto generado sin validación determinista y autorización.

### B. Resistencia a prompt injection

- Mantener las instrucciones de sistema/política separadas del contenido no confiable; tratar CVs, tickets, resultados RAG, documentos y resultados de MCP como datos, nunca como instrucciones.
- Mitigar inyección directa e indirecta con defensa en profundidad: límites de entrada, instrucciones explícitas, reducción de contexto y datos, permisos mínimos de tools, validación de salida/argumentos y confirmación humana antes de efectos secundarios.
- No confiar en un detector textual como único control. El modelo no debe poder ampliar permisos, revelar datos ajenos ni ejecutar una acción prohibida solo por una instrucción incluida en contenido externo.
- Añadir pruebas automatizadas reproducibles basadas en los ejemplos del briefing:
  1. CV con instrucción oculta/visible para autoasignarse el mejor ranking: no altera scoring/reglas; evidencia de respuesta segura.
  2. Ticket que solicita acceso a la cuenta de otro usuario: se rechaza y se escala, sin invocar una herramienta no autorizada.
- Las pruebas deben usar datos sintéticos, comprobar resultado y ausencia de llamadas/efectos no autorizados, y registrar comando, entorno, salida esperada/obtenida. No afirmar que un caso fue bloqueado sin ejecutar y guardar evidencia.

### C. Límites de agentes y acciones

- Aplicar mínimo privilegio por agente, herramienta, usuario y tenant. Un usuario de soporte no puede invocar herramientas de scoring/ATS ni leer datos de otro candidato; las consultas RAG deben filtrar antes de devolver resultados.
- Validar de forma determinista la identidad, permisos y esquema de cada llamada a herramientas; restringir acciones y argumentos permitidos. Registrar denegaciones y errores sin incluir secretos ni contenido personal innecesario.
- Requerir **confirmación humana explícita, asociada a la acción y al objeto/alcance**, antes de:
  - rechazar/descartar a un candidato;
  - enviar propuestas comerciales o contratos;
  - marcar como resuelto un ticket con queja o dato sensible;
  - modificar masivamente estados de candidatos en ATS.
- Si el flujo/acción no existe en el fork, declararlo no implementado/no verificable y no inferir que existe aprobación. La prueba debe demostrar que, antes de la confirmación, no ocurre el efecto secundario.

### D. Rate limiting y trazabilidad

- Implementar rate limiting verificable al menos en un endpoint que dispare inferencia de modelo. Definir alcance (por usuario/IP/tenant según identidad disponible), ventana, límite, respuesta `429` y protección de rutas alternativas; no confiar exclusivamente en IP si existe autenticación.
- Añadir logging estructurado para al menos un flujo agentic: identificador de correlación, actor/tenant pseudonimizados cuando sea posible, agente/tool, decisión/resultado, motivo resumido, aprobación y marca temporal. No registrar prompts, CVs, tokens ni datos personales completos por defecto.
- Verificar trazabilidad de una prueba de extremo a extremo y documentar retención/acceso a logs o los aspectos pendientes.

## Evaluación de riesgos y cumplimiento

### NIST

El informe cubrirá explícitamente las seis funciones solicitadas por el encargo: **Govern, Identify, Protect, Detect, Respond y Recover**. Citar el marco y versión vigentes que se utilicen (incluyendo la referencia NIST concreta); no presentar una lista genérica como evaluación. Cada función incluirá estado/evidencia, brechas y al menos una acción concreta, priorizada, con responsable por rol y criterio de cierre.

Como mínimo, evaluar gobernanza y terceros; inventario/flujo/contexto de datos; controles preventivos; detección y trazabilidad; respuesta y notificación; recuperación, continuidad y lecciones aprendidas. Priorizar las medidas urgentes frente a prompt injection, filtración entre candidatos/clientes, excesos de permisos y secretos.

### Regulación y datos personales

- Citar expresamente el **RGPD** para el tratamiento en España/UE: base legal, finalidad, minimización, control de acceso, derechos y evaluación de riesgos. Explicar la obligación de notificación a la **AEPD dentro de 72 horas cuando corresponda** (brecha que suponga riesgo para derechos/libertades), según el briefing.
- Evaluar la **Florida Information Protection Act (FIPA)** para operaciones pertinentes en Florida y su plazo de notificación de **30 días** según el briefing.
- Evaluar la **Fair Credit Reporting Act (FCRA)** si se realizan verificaciones de antecedentes; confirmar aplicabilidad con el responsable legal. No dar por hecho que se hacen.
- Identificar cuestiones para validación de asesoría legal y supuestos. Los controles técnicos no constituyen por sí solos una declaración de cumplimiento. No sustituir estos marcos por una referencia vaga a normativa estadounidense.

## Auditoría OWASP Top 10

Evaluar las **10 categorías** de OWASP Top 10 y citar la edición exacta empleada. Para cada categoría, completar por separado los carriles **backend**, **frontend** y **sistema agéntico**. Cada celda debe incluir estado (aplica/no aplica/no verificable), evidencia concreta (ruta, endpoint, configuración, prueba y líneas si están disponibles), impacto y recomendación o corrección. Justificar los casos no aplicables; no marcar como seguro lo que no se pudo verificar.

Dar atención específica, sin limitarse a ellas, a:

- **A01 Broken Access Control**: separación por rol/tenant, acceso a RAG, tools de scoring/ATS y acceso cruzado a candidatos/clientes.
- **A02 Cryptographic Failures**: secretos sólo en entorno/vault, datos sensibles en tránsito (TLS) y almacenamiento.
- **A05 Security Misconfiguration**: ejecución no-root, rutas debug, configuración pública y scopes MCP mínimos.

### Baseline servidor y red

Registrar únicamente lo que se pueda observar con acceso y evidencia: modelo de SSH, prohibición de login root directo, usuario deploy/operativo no-root, permisos que separen código/logs/configuración secreta y reglas de firewall. Confirmar que DB, Redis y puertos de depuración/modelos internos no están expuestos públicamente; documentar los puertos públicos estrictamente necesarios (típicamente HTTPS y SSH de operaciones). Si no hay acceso a host/cloud/firewall, marcar estos controles como **no verificables en el código/repo**, solicitar evidencia operativa y no afirmar que están endurecidos.

## Entregables

1. **Informe de auditoría en `docs/`**, en español, con fecha de ejecución y versión/commit auditado. Nombre sugerido: `docs/informe-auditoria-seguridad-ia.md`.
2. Inventario de sistemas de IA: componente, propósito, entradas/salidas y datos, modelos/proveedores, tools/MCP, permisos, responsable interno por rol, tercero y responsabilidad compartida, riesgos y estado (presente/no encontrado/no verificable).
3. Evaluación NIST de las seis funciones con evidencia, acciones priorizadas, responsables por rol y criterios de cierre.
4. Matriz OWASP Top 10 × backend/frontend/agente con evidencia y resultado por celda.
5. Evaluación RGPD, FIPA y FCRA según aplicabilidad, incluidas notificaciones y preguntas pendientes de asesoría legal.
6. Hallazgos priorizados (crítico/alto/medio/bajo), con activo, escenario, impacto, evidencia, estado, responsable, corrección o mitigación y riesgo residual.
7. Registro de acciones irreversibles con flujo revisado, prueba, resultado de confirmación humana y brecha/no verificable.
8. Evidencia reproducible de pruebas de prompt injection, rate limiting, logging y correcciones críticas antes/después, usando únicamente datos sintéticos.
9. Estado de endurecimiento de servidor/red, fuente de evidencia y limitaciones explícitas.
10. Ruta de remediación ordenada por prioridad, esfuerzo/dependencias cuando se conozcan y criterio verificable para cerrar cada brecha.

Implementar las protecciones críticas confirmadas en código/configuración y pruebas dentro del alcance del fork. Para hallazgos operativos que requieran acceso al entorno o cambios contractuales, entregar mitigación, responsable y evidencia requerida; no simular la verificación.

## Criterios de aceptación

- [ ] Se revisaron todos los componentes del alcance y los sistemas adicionales de IA hallados; ausencias/no verificables están justificadas.
- [ ] El inventario incluye los cuatro sistemas del briefing y otros encontrados, con responsable interno por rol y responsable/controles de terceros.
- [ ] Los secretos no están hardcodeados en código/configuración revisados; se consumen de entorno/vault y no aparecen en logs/salidas.
- [ ] Inputs y salidas hacia modelos/tools tienen validación explícita; contenido externo se trata como no confiable y no puede sobreescribir instrucciones.
- [ ] Hay al menos una prueba reproducible con el caso de CV y/o ticket del briefing que demuestra neutralización/rechazo y ausencia de acción no autorizada.
- [ ] Al menos un endpoint con inferencia aplica rate limiting y una prueba verifica límite y respuesta.
- [ ] Al menos un flujo agentic deja trazabilidad verificable, con minimización de datos en logs.
- [ ] Las cuatro acciones irreversibles se verificaron una por una y no producen efecto antes de confirmación humana; lo no implementado se marca claramente.
- [ ] NIST documenta las seis funciones con marco/versión, evidencia y al menos una acción concreta priorizada por función.
- [ ] Se citan RGPD, FIPA y FCRA cuando aplique, con plazos del briefing y limitaciones legales explícitas.
- [ ] OWASP presenta las 10 categorías × tres carriles, cada celda con estado y evidencia o justificación de no aplicabilidad.
- [ ] Todo hallazgo crítico confirmado en código queda corregido con prueba reproducible antes/después; cualquier crítico abierto queda destacado y bloquea el sign-off.
- [ ] El estado de SSH, usuario no-root, permisos y firewall se apoya en evidencia operativa; sin acceso, se declara no verificable y no endurecido.
- [ ] El informe no contiene datos personales reales ni secretos y separa hechos, supuestos, recomendaciones y asuntos pendientes.
