# Spec: auditoría de ciberseguridad e integración segura de IA

## Contexto

Realizar una auditoría de seguridad del fork de Nexova y proponer o implementar las correcciones necesarias antes de dar el sistema por aprobado. La auditoría debe cubrir tanto las aplicaciones web como los componentes de IA y sus integraciones.

Fuentes del encargo:

- [Briefing de ciberseguridad](../docs/cibersecurity-audit-briefing.md)

## Alcance

Auditar, según los componentes existentes en el fork:

- Pipeline de selección asistida por IA, incluido el scoring de CVs.
- Búsqueda RAG sobre perfiles de candidatos.
- Agente de soporte de primera línea para outsourcing.
- Agente de prospección comercial.
- Backend/API, dashboards y frontend.
- Endpoints MCP y proxies de modelos.
- Configuración del servidor y de red: acceso SSH, usuario operativo, permisos y firewall.

Los cuatro sistemas de IA del inventario del briefing deben aparecer en el informe con un responsable asignado, aunque algún componente no exista o no esté habilitado en el fork. En esos casos, indicar «no encontrado» o «no aplica» y justificarlo con evidencia.

## Requisitos

### 1. Informe de riesgos de IA según NIST

- Aplicar y citar explícitamente un marco NIST adecuado para la gestión de riesgos de IA; indicar el marco y la versión utilizados.
- Incluir el inventario de los cuatro sistemas del briefing, su función, responsable, datos tratados y principales riesgos.
- Evaluar filtración entre candidatos/clientes, prompt injection, exceso de permisos y trazabilidad de decisiones.
- Demostrar al menos una prueba de prompt injection basada en los casos del briefing, bloqueada o neutralizada, con evidencia reproducible.
- Verificar y documentar que las acciones irreversibles enumeradas abajo requieren confirmación humana en la implementación actual.
- Identificar los controles faltantes y diferenciar con claridad hallazgos observados de recomendaciones.

### 2. Privacidad y regulación

- Citar el RGPD como marco aplicable al tratamiento de datos personales en España/UE; evaluar base legal, minimización, acceso y respuesta a brechas, incluida la notificación a la AEPD dentro de 72 horas cuando corresponda.
- Evaluar FIPA para operaciones en Florida y su plazo de notificación de 30 días cuando resulte aplicable.
- Evaluar FCRA si el proceso incluye verificaciones de antecedentes.
- No afirmar cumplimiento legal solo por la existencia de controles técnicos. Señalar supuestos y cuestiones que requieren validación legal.
- Tratar CVs, historial laboral, pretensiones salariales, datos de empleados y contactos comerciales como información sensible para el análisis; no incluir datos personales reales en evidencias o ejemplos.

### 3. Auditoría OWASP Top 10

- Evaluar las 10 categorías de OWASP Top 10, indicando la edición utilizada.
- Analizar cada categoría por separado para los carriles backend, frontend y sistema agéntico.
- Para cada evaluación, registrar «aplica» o «no aplica», evidencia concreta (archivo, endpoint y líneas cuando estén disponibles), impacto y recomendación o corrección.
- Priorizar, entre otros, control de acceso entre roles y candidatos, protección de secretos y datos en tránsito, y configuración de agentes, herramientas y scopes MCP.
- Corregir todo hallazgo crítico confirmado y aportar evidencia reproducible de antes y después mediante pruebas, escaneos o comandos seguros.

### 4. Endurecimiento de servidor

- Documentar el modelo de acceso SSH y verificar que no se permita inicio de sesión directo como root.
- Verificar un usuario operativo dedicado y no-root.
- Documentar permisos explícitos que separen código, logs y configuración sensible.
- Verificar reglas de firewall: exponer únicamente los puertos necesarios (por ejemplo, HTTPS y SSH de operaciones) y mantener cerrados los puertos internos de base de datos, Redis, depuración y modelos.
- Registrar la evidencia de configuración observada; no declarar endurecido un servidor basándose únicamente en recomendaciones o configuración no verificada.

### 5. Confirmación humana para acciones irreversibles

Comprobar que la implementación requiere confirmación humana antes de:

- Rechazar automáticamente a un candidato.
- Enviar una propuesta comercial o contrato.
- Resolver un ticket que involucre una queja o datos sensibles.
- Cambiar masivamente el estado de candidatos en el ATS.

Si una acción no está implementada, documentarla como no verificada; no inferir que existe el control.

## Entregables

Un informe de auditoría en `docs/` que incluya:

1. Resumen ejecutivo, alcance, fecha, supuestos, limitaciones y responsables.
2. Inventario de sistemas de IA y asignación de responsables.
3. Evaluación NIST de riesgos de IA y evidencias de las pruebas de prompt injection.
4. Evaluación regulatoria de RGPD, FIPA y FCRA, según aplicabilidad.
5. Matriz OWASP Top 10 por backend, frontend y agente, con evidencia para cada categoría.
6. Estado del endurecimiento de servidor y evidencia de acceso, permisos y puertos.
7. Matriz de acciones irreversibles y resultado de la comprobación de confirmación humana.
8. Registro de hallazgos con severidad, impacto, evidencia, estado y recomendación.
9. Evidencia reproducible antes/después para cada hallazgo crítico corregido, y resultados de pruebas ejecutadas.

## Criterios de aceptación

- [ ] Se auditan todos los componentes del alcance o se justifica explícitamente que no existen/no aplican.
- [ ] El informe identifica y cita el marco y versión NIST y la edición de OWASP empleadas.
- [ ] El inventario contiene los cuatro sistemas de IA y un responsable asignado para cada uno.
- [ ] Se documenta al menos un caso de prompt injection bloqueado o neutralizado con evidencia reproducible.
- [ ] Las cuatro acciones irreversibles tienen un resultado explícito de verificación de confirmación humana.
- [ ] Las 10 categorías OWASP tienen resultado y evidencia por cada carril backend, frontend y sistema agéntico.
- [ ] Cada hallazgo crítico confirmado queda corregido y demostrado antes/después; los hallazgos no corregidos se identifican claramente y bloquean el sign-off.
- [ ] La configuración SSH, el usuario no-root, los permisos y las reglas de firewall se verifican con evidencia, no solo con recomendaciones.
- [ ] El informe evita datos personales reales y distingue hallazgos, supuestos y recomendaciones legales.
