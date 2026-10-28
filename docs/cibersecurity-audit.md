# Auditoria de ciberseguridad de Nexova

Fecha: 2026-10-28. Base inspeccionada: `7e42ec2`.
Estado: **NO APROBADO**. Auditoria local terminada con riesgos residuales y
verificaciones de produccion pendientes. No es una certificacion legal.
No se han consultado datos personales, credenciales ni servicios de terceros
con informacion del repositorio. Los ejemplos y pruebas usan datos sinteticos.

## Evidencia critica: SEC-01, lectura arbitraria de archivos

Severidad critica, confianza 10/10. Antes de la correccion,
`server.py:113-126` registraba `GET /{path:path}` sin autenticacion y construia
una ruta con `os.path.join` sobre la raiz del proyecto. Exponia archivos
internos, directorios con `index.html`, enlaces simbolicos y traversal.
Impacto: posible descarga de configuracion, claves y bases locales y,
por tanto, compromiso de cuentas. No se descargaron esos archivos reales.

Reproduccion previa ejecutada: extraccion AST de la funcion real en una app
FastAPI minima, con `httpx.ASGITransport`, raiz y canarios temporales.

```text
/private-canary.txt: status=200, synthetic_canary_exposed=True
/..%2Foutside-canary.txt: status=200, synthetic_canary_exposed=True
```

Correccion: retirar el catch-all que servia la raiz del repositorio; no
intentar filtrar extensiones o normalizar traversal manteniendo la exposicion.
Las interfaces se sirven separadamente; se conserva `GET /` y el registro
de routers de la API. Una URL no registrada devuelve ahora 404.

Regresion reproducible sin credenciales ni red:

```sh
python -m pytest tests/security/test_static_files.py -q
```

La suite crea exclusivamente archivos temporales sinteticos (incluido un
archivo **falso** llamado `.env`), un enlace y un archivo fuera de la raiz.
Ejecuta las funciones reales extraidas por AST, sin inicializar proveedores,
bases del proyecto ni el lifespan completo. Verifica cuatro archivos privados,
traversal codificado, enlaces y conservacion del indice publico. Esta prueba
aislada no sustituye un smoke test del servidor completo.

Resultado posterior: **7 passed**; todas las peticiones a archivos privados,
traversal y enlaces devuelven 404, el indice devuelve 200. Ruff E9 sobre
servidor/pruebas y F sobre pruebas, y `git diff --check`: aprobados.

## Contencion operativa y confirmacion humana

Politica autorizada por el desarrollador: incidencias, analizador y API del
agente quedan limitados a `admin`/`manager`. Inventario exige autenticacion
en lecturas y roles operativos en escrituras; MCP autentica tambien sus GET
de productos con el token de servicio. No se afirma aislamiento por cliente:
el modelo de incidencias no contiene un tenant verificado y los operadores
autorizados comparten el conjunto de datos.

Toda resolucion de ticket requiere `confirm_resolution: true` (booleano
estricto), un actor autenticado y transicion valida. La UI solicita confirmacion;
se persisten `resolved_by` y `resolution_confirmed_at`. No se permite crear
directamente un ticket ya resuelto. MCP rechaza `resolved` antes de llamar
al backend incluso si el cliente tiene scope de escritura.
Esto verifica una confirmacion explicita en el flujo implementado, no una
prueba criptografica de presencia humana: un cliente API privilegiado puede
enviar el booleano. Separar identidades humanas/de servicio y doble aprobacion
es una recomendacion pendiente.

Pruebas offline reproducibles:

```sh
PYTHON_DOTENV_DISABLED=1 SECRET_KEY=synthetic-audit-only \
  python -m pytest tests/security/test_operations_controls.py \
  tests/security/test_briefing_injection.py tests/mcps/test_backend.py \
  tests/mcps/test_server.py -q
```

La prueba del briefing envia literalmente la instruccion de olvidar politicas
y acceder a otra cuenta. Exige bloqueo `instruction_override`, cero consultas
a RAG/LLM/tools, traza sin texto del ataque y respuesta de rechazo. No acredita
robustez universal frente a variantes ni escalacion automatica del caso;
esa escalacion no esta implementada.

Resultado: **38 passed** en controles operativos, caso de inyeccion, backend
MCP, servidor MCP y regresion de inventario. Ruff E9 y F en pruebas nuevas:
aprobados. ESLint focalizado: cero errores, dos warnings previos en
`services/api.ts` (variables no usadas).

Typecheck global intentado una vez: falla por cinco errores preexistentes en
`__tests__/services/rfp-sse.test.ts` (vitest ausente), `hooks/useRfpSse.ts`
(dos imports inexistentes), `services/chat-ws.ts` (`JWT_TOKEN_KEY` inexistente)
y `services/rfp-sse.ts` (reader posiblemente undefined). No se corrigieron
fuera de alcance. Un tsconfig temporal que extiende el original, limita
`include` a los archivos afectados y conserva `strict` verifica sus imports
transitivos correctamente. No se afirma que el build global pase.

## Credenciales de login

Antes: la ruta Next.js serializaba email/password con `URLSearchParams` en
`POST /login?...`, y FastAPI esperaba parametros query. Una peticion POST
no oculta una query de los access logs, proxies o herramientas de observacion.
Despues: `POST /login` requiere `LoginRequest` en JSON y el proxy envia
ese cuerpo, nunca credenciales en la URL. Los clientes directos deben migrar
a JSON; no se mantiene fallback query por seguridad. El cuerpo sigue
requiriendo TLS y redaccion de logs en el despliegue.

```sh
PYTHON_DOTENV_DISABLED=1 SECRET_KEY=synthetic-audit-only \
  python -m pytest tests/security/test_login_transport.py -q
cd uis/backoffice
npm exec --no -- jest --runInBand __tests__/api/login-route.test.ts
```

Resultado: **5 passed** backend; **24 passed** en dos suites Jest (proxy nuevo
y cliente de autenticacion existente). ESLint, Ruff focalizados, typecheck del
area y diff check aprobados. El primer intento backend rechazo el dominio
reservado `.test` del ejemplo; se sustituyo solo el dato sintetico por
`example.com`, sin llamadas de red, y la repeticion paso.

## Canales secundarios: tokens y notificaciones RFP

SEC-05 (alta, confianza 10/10): el proxy publico de candidatos conservaba
`Authorization` recibido; el cliente usa ese header para su JWT local.
Correccion: eliminar Authorization y Cookie con `Headers`, sin depender de
mayusculas/minusculas, antes de llamar al Playground. Tres pruebas mockeadas
verifican que ningun token sale de la aplicacion; no se contacto al proveedor.
El Playground sigue siendo un dataset publico: **no usar datos personales
reales**. Su autenticacion, retencion y base legal no se certifican.

SEC-06 (media, confianza 10/10): el gestor SSE difundia eventos de creacion
RFP a cualquier suscriptor autenticado, aunque los tickets REST estan
restringidos. El payload actual contiene IDs, fecha y estado, pero metadatos
de cliente aun nulos: no se afirma exposicion de documentos por este canal.
Correccion: publicar y suscribir por el ID autenticado del propietario;
se conserva entrega a varias pestanas propias y se excluyen otros usuarios.
Una prueba offline comprueba dos pestanas propias y una ajena.

Resultado de la regresion de recepcion/aprobacion RFP y SSE: **14 passed**.
Proxy: **3 passed**; ESLint, Ruff y typecheck estricto del area aprobados.

## 1. Resumen ejecutivo, alcance y limitaciones

Se corrigio el unico critico confirmado, SEC-01, y se reforzaron permisos,
confirmacion humana, login, salida de credenciales y aislamiento SSE. Seis
hallazgos de codigo se detallan abajo; SEC-03 queda mitigado, no resuelto
en cuanto a segregacion entre clientes. Los commits de correccion son:
`53a8d5f`, `2948e8e`, `a3b7b39` y `e1f33e6`.

Metodo: revision estatica del fork actual, pruebas offline con mocks y datos
sinteticos, comprobaciones de solo lectura del Codespace y consulta de fuentes
oficiales publicas. No se hicieron pentests contra Internet, consultas a
cuentas reales, lecturas de bases reales, escaneos de red ni cambios del host.
No se ejecutaron modelos remotos ni se enviaron documentos a proveedores.
El ambito es el codigo disponible, no una API externa ni un despliegue no
identificado. Ausencia de un componente no equivale a control implementado.

Cobertura:

- Backend: FastAPI, usuarios/perfiles, proveedores, inventario, incidencias,
  analizador CSV, telemetria, reporting, conocimiento, RFP y superficie chat.
- Frontend: backoffice Next.js, proxies, pipeline tracker y website estatico.
  El tracker usa el Playground externo, no un ATS propio auditable.
- IA: RAG comercial, agente de soporte con memoria/guardrails/MCP y RFP
  con generacion/aprobacion departamental. Scoring CV, RAG de candidatos y
  prospeccion autonoma no encontrados como implementaciones ejecutables.
- MCP: `mcps/server.py`, `mcps/backend.py`, cliente del agente y pruebas.
  Algunos resultados del arbol MCP y la guia local de Next estan excluidos
  por politica organizativa; no se accedio ni se reconstruyo su contenido.
- Infraestructura: Dockerfiles/Compose y observaciones locales. No hay
  acceso autorizado al servidor final, panel cloud, reverse proxy ni firewall
  perimetral. Por tanto **no se verifica endurecimiento en produccion**.

Bloqueo de integracion preexistente comprobado: el chat importa
`verify_jwt_token` desde [auth.py](../services/api/users/auth.py), donde no
existe; [routes.py](../services/api/chat/routes.py) tambien importa
`get_session`, ausente en [database.py](../services/database.py), que ofrece
`get_db`. El primer import se comprobo sin arrancar servicios. No se modifica
esta integracion ajena a las correcciones; impide acreditar un smoke test del
servidor completo. Las pruebas de routers nuevas usan una app minima real;
las de archivos extraen las funciones reales con AST.

Responsabilidad de remediacion: CTO/Infraestructura para backend, MCP,
despliegue e identidades; responsables de dominio para autorizaciones y
decisiones humanas; responsable de privacidad/asesoria para legalidad.
Son asignaciones funcionales de este informe, pendientes de aceptacion formal,
no una afirmacion de designaciones organizativas ya existentes.

## 2. Inventario obligatorio de IA

| Sistema del briefing | Funcion y estado observado | Responsable funcional asignado | Datos tratados / previstos | Riesgos y evidencia |
| --- | --- | --- | --- | --- |
| Pipeline de seleccion/scoring CV | **No encontrado**. Hay CRUD frontend de candidatos; no extraccion, scoring ni ranking ejecutables encontrados en services, pipelines o agents. | Responsable de Operaciones de Seleccion | Previstos: CV, historial, evaluaciones, salario; no se leyeron registros reales. | Sesgo, leakage y rechazo automatico sin trazabilidad si se implementa. [Cliente del tracker](../uis/backoffice/services/api.ts), [tipos](../uis/backoffice/types/candidate.ts); busqueda `scoring/ranking/curriculum` no identifica un motor. |
| RAG sobre candidatos | **No encontrado**. El RAG existente indexa cuatro documentos comerciales, no perfiles. No asumir equivalencia. | CTO / Responsable de Datos | Actual: servicios, precios, SLA, objeciones; previsto: perfiles y contactos. | ACL por candidato/cliente ausente para un hipotetico RAG personal. [SOURCE_DOCUMENTS, lineas 24-29](../data_project/process/knowledge_base.py#L24), [API knowledge](../services/api/knowledge/routes.py). |
| Agente de soporte outsourcing | **Encontrado**, agente interno LangGraph, fuentes RAG/incidencias/inventario, memoria aprobada y trazas. Resolucion automatica no habilitada desde sus tools de consulta; MCP tiene otras escrituras limitadas. | Responsable de Outsourcing/Soporte | Preguntas, documentos, datos operativos; memorias por customer_id; checkpoints con estado de ejecucion. | Inyeccion, cliente arbitrario, scopes de servicio compartidos y retencion de estado. [Grafo](../services/agent/support.py), [guardrails](../services/agent/guardrails.py), [MCP](../mcps/server.py). |
| Agente de prospeccion comercial | **No encontrado** como agente que redacta/envia seguimientos a prospectos. RAG comercial y RFP son capacidades relacionadas, no ese agente. | Direccion Comercial | Previstos: contactos, negociaciones e historial comercial. Actual RFP: PDFs, requisitos, borradores y aprobaciones. | Mezcla de clientes, envio no autorizado, contenido inventado. [RFP](../data_project/pipelines/rfp_intake/), [RAG](../data_project/pipelines/rag.py); agents solo aporta plantilla Python. |

Componente adicional observado: RFP convierte PDFs y genera respuestas por
departamento; valida evidencia, digests y aprobaciones antes de generar el
documento final. No hay prueba de envio externo de ese documento. Los
responsables de aprobacion dependen de roles configurados; actualmente un
admin global puede aprobar todas las secciones.

## 3. Evaluacion NIST de riesgos de IA

Marco utilizado: **NIST AI RMF 1.0, NIST AI 100-1 (enero de 2023)**;
complemento **Generative AI Profile, NIST AI 600-1 (julio de 2024)**.
Se usa explicitamente la version 1.0 aunque el sitio NIST anuncia revision;
no se afirma emplear un borrador posterior ni certificar conformidad.
Fuentes oficiales: [AI RMF](https://www.nist.gov/itl/ai-risk-management-framework),
[AI 100-1](https://doi.org/10.6028/NIST.AI.100-1),
[AI 600-1](https://doi.org/10.6028/NIST.AI.600-1).

| Funcion | Observado | Brecha / accion y responsable |
| --- | --- | --- |
| GOVERN | Roles admin/manager/user; cambios de memoria requieren aprobador; decisiones RFP persistidas. | Aceptar formalmente responsables, apetito de riesgo, inventario de proveedores y politica de uso de PII. CTO + responsables de negocio/privacidad. |
| MAP | RAG comercial delimitado a cuatro fuentes; herramientas operativas identificadas; scoring y prospeccion no encontrados. | Mapear tenant y finalidades antes de incorporar CVs, contactos o clientes reales. Responsable de Datos + cada dominio. |
| MEASURE | Caso literal del briefing bloqueado; tests de esquemas, permisos, MCP y SSE. | Medir variantes indirectas/multilingues, fuga entre clientes, sesgo y falsos positivos; ninguna metrica de equidad CV verificada. Soporte + Seleccion. |
| MANAGE | Cierre MCP bloqueado, confirmacion explicita en UI/API, respuesta segura y trazas de guardrails. | Validar autorizacion de customer_id, identidades humanas/de servicio y revocacion; runbook de brechas y controles de despliegue. CTO/Infraestructura. |

Riesgos prioritarios:

1. **Filtracion entre candidatos/clientes:** no se prueba aislamiento del
   Playground ni de un RAG personal inexistente. En soporte, `customer_id`
   procede del cuerpo de peticion; [API](../services/agent/routes.py) no
   verifica pertenencia a un cliente y [memoria](../services/agent/memory.py)
   filtra por ese identificador, no por una relacion de autorizacion del actor.
   Restringir a operadores reduce exposicion, pero no es segregacion tenant.
2. **Prompt injection:** guard determinista y salida estructurada en agente,
   instrucciones y datos separados en [generate_support_reply, linea 208](../data_project/pipelines/rag.py#L208).
   No equivale a inmunidad; `/knowledge/query` usa otro flujo, sin aplicar
   todos los guardrails del agente. Los PDFs RFP son datos no confiables.
3. **Exceso de permisos:** MCP valida issuer/audience/scopes y paths fijos,
   pero se conecta al REST con identidad de servicio compartida. El agente
   usa solo tools de consulta; inventario write es rechazado; resolver tickets
   desde MCP queda bloqueado incluso con `incidents:write`.
4. **Trazabilidad:** trazas sanitizadas con run_id, checkpoints SQLite,
   auditoria de memoria y decisiones/digests RFP. No hay evidencia de logs
   inmutables, alertas, revisiones de sesgo ni politica integral de retencion.
   Una traza sanitizada no implica que el checkpoint omita la pregunta/contexto.

### Caso de inyeccion y limites de la evidencia

La prueba versionada [test_briefing_injection.py](../tests/security/test_briefing_injection.py)
envia el ataque del ticket descrito arriba, con transportes/fuentes sustituidos
por mocks que fallan si se usan. Resultado: bloqueo antes de RAG, LLM,
incidencias o inventario; un evento `input_guardrail`, categoria `security`,
accion `blocked`, sin almacenar el texto en la traza.
El caso del CV no se ejecuta porque el pipeline no existe.
La prueba indirecta existente de [guardrails](../tests/pipelines/test_support_agent_guardrails.py)
comprueba la separacion system/user con un proveedor simulado: **no demuestra**
que un LLM remoto resistiera la inyeccion. La escalacion humana automatica
de un ataque sigue sin implementarse.

## 4. Privacidad y regulacion

CVs, historial laboral, pretensiones salariales, evaluaciones, datos de
empleados y contactos comerciales se consideran **sensibles para este
analisis**. No todos constituyen categorias especiales del articulo 9 RGPD;
si incluyen salud, afiliacion u otras categorias del articulo 9, requieren
analisis adicional. No se incluyen personas reales en las evidencias.

| Marco | Aplicabilidad y evaluacion | Pendiente de validacion legal/operativa |
| --- | --- | --- |
| **RGPD**, Reglamento (UE) 2016/679 | Aplica al tratamiento de datos personales en Espana/UE (art. 3). Arts. 5/6: finalidad, minimizacion y base legal por proceso; no se encontro evidencia suficiente de registro de tratamientos ni base legal documentada para cada uso IA. | Determinar responsables/encargados, bases legales, informacion a interesados (13/14), derechos y plazos, retencion/borrado, contratos de encargados (28), seguridad (32), EIPD cuando proceda (35) y transferencias UE/EEUU (44 y siguientes). La expansion a Miami no demuestra transferencia valida. |
| **Brechas RGPD**, arts. 33/34 | Notificar a AEPD sin dilacion indebida y, de ser posible, dentro de **72 horas desde tener constancia**, salvo que sea improbable riesgo para derechos/libertades; justificar retrasos. Encargado informa sin dilacion al responsable. | Documentar todas las brechas; notificar tambien a afectados si hay alto riesgo, con excepciones legales. No hay simulacro ni procedimiento 24/7 acreditado. |
| **FIPA**, Florida Statutes 501.171 | Condicional a datos/individuos de Florida y definicion legal de personal information/breach; no todo contacto comercial activa identicas obligaciones. Notificacion a afectados, en general, sin demora indebida y maximo **30 dias** desde determinar o tener razon para creer que hubo brecha, con excepciones legales. | Si afecta a **500 o mas** personas de Florida, aviso al Department of Legal Affairs en ese plazo; valorar demoras/extension legal, agentes terceros y otras notificaciones. Asesoria debe evaluar cada incidente; no se sustituye AEPD por Florida ni viceversa. |
| **FCRA**, 15 USC 1681 y siguientes | **No aplica al flujo observado**: no se encontro proveedor de consumer/background reports ni verificacion de antecedentes implementada. Aplicabilidad futura condicional, no exencion general para Nexova. | Antes de contratar informes de antecedentes para empleo: aviso separado, autorizacion escrita, certificacion al proveedor, pre-adverse action con copia/derechos y adverse action final cuando proceda. Validar supuestos y normas estatales/locales con asesoria. |
| Decisiones automatizadas, RGPD art. 22 | No hay rechazo automatico CV implementado que se pueda verificar. Aprobaciones RFP y confirmacion de ticket no prueban revision humana de seleccion. | Antes de scoring real, evaluar efectos significativos, derecho a intervencion humana, explicacion/impugnacion y sesgo. No habilitar rechazo automatico solo por disponer de un checkbox. |

Fuentes: [texto oficial RGPD](https://eur-lex.europa.eu/eli/reg/2016/679/oj),
[FIPA oficial, apartados 1, 3 y 4](https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0500-0599/0501/Sections/0501.171.html),
[guia conjunta EEOC/FTC sobre antecedentes](https://www.eeoc.gov/laws/guidance/background-checks-what-employers-need-know).
NIST/OWASP, FIPA y guia EEOC se recuperaron durante la auditoria.
EUR-Lex no devolvio texto util al fetch; el enlace se conserva como referencia
normativa, no como evidencia de una comprobacion automatica del texto.
Los controles tecnicos descritos **no acreditan cumplimiento legal**.

## 5. Matriz OWASP Top 10 por carril

Edicion seleccionada: **OWASP Top 10:2021**, la que utiliza los identificadores
A01/A02/A05 del briefing. No se presenta como la edicion mas reciente.
[Listado oficial](https://owasp.org/Top10/2021/). Es una taxonomia web; la
inyeccion de prompts se evalua adicionalmente bajo NIST, no como SQLi probada.
Treinta evaluaciones independientes; "aplica" indica superficie pertinente,
no vulnerabilidad confirmada. "No observado" no significa "seguro".

| Categoria | Carril / aplicabilidad | Evidencia concreta | Impacto / resultado | Correccion o recomendacion |
| --- | --- | --- | --- | --- |
| A01 Control de acceso roto | Backend: aplica | [inventory/routes.py](../services/api/inventory/routes.py), `/inventory/products`; [incidents/routes.py](../services/api/incidents/routes.py), `/api/incidents`; [rfp sse](../services/api/rfp_intake/sse.py) | Escritura anonima y eventos cruzados corregidos; incidencias aun sin tenant. | SEC-02/03/06; mantener control por objeto y migrar tenancy antes de PII real. |
| A01 Control de acceso roto | Frontend: aplica | [middleware.ts:7-20](../uis/backoffice/middleware.ts#L7), [records proxy](../uis/backoffice/app/api/records/_shared.ts) | Cookie existente no verifica identidad; `/api` es publico en middleware; proveedor de candidatos publico. | No usar middleware como autorizacion; backend valida permisos. Solo datos demo en Playground. |
| A01 Control de acceso roto | Agente: aplica | [agent/routes.py](../services/agent/routes.py), `POST /agent/query`, `/traces/{run_id}`; [memory.py](../services/agent/memory.py) | Ahora requiere operador; customer_id sigue suministrado por actor y trazas compartidas entre operadores. | SEC-03 mitigado; verificar pertenencia de cliente y propiedad de trazas. |
| A02 Fallas criptograficas | Backend: aplica | [auth.py:21-45](../services/api/users/auth.py#L21), [login](../services/api/users/routes.py), [Compose](../docker-compose.yml) | bcrypt y JWT con secreto requerido; login query eliminado; TLS final no verificado. | SEC-04; vault, rotacion, TLS y cifrado de datos/backups. |
| A02 Fallas criptograficas | Frontend: aplica | [auth-token.ts:5-7](../uis/backoffice/lib/auth-token.ts#L5), [records proxy](../uis/backoffice/app/api/records/_shared.ts) | JWT en localStorage/cookie accesible a JS; no Secure/HttpOnly; fuga a proveedor corregida. | SEC-05; evolucionar a sesion HttpOnly con CSRF y CSP; verificar HTTPS. |
| A02 Fallas criptograficas | Agente: aplica | [support.py](../services/agent/support.py), SQLite/checkpointer; [mcp_tools.py:27-55](../services/agent/mcp_tools.py#L27) | Credenciales desde entorno; HTTP permitido por configuracion; checkpoints contienen estado. | TLS en redes no confiables, permisos, cifrado, retencion y redaccion. No se inspeccionaron claves. |
| A03 Inyeccion | Backend: aplica | [memory.py:348-364](../services/agent/memory.py#L348), consultas parametrizadas; [upload PDF:242](../services/api/rfp_intake/routes.py#L242) | Parametrizacion observada y PDF con limites; no SQLi ni ejecucion de comandos por entrada confirmadas. | Mantener parametros, limites y aislamiento de parsing PDF. |
| A03 Inyeccion | Frontend: aplica | [IncidentsManagerClient](../uis/backoffice/components/IncidentsManagerClient.tsx), React; [website](../uis/website/application.html) | Renderizado React no prueba ausencia de XSS; website referencia validation.js, no encontrado en raiz. | Verificar validacion servidor y CSP; no confiar en validacion del navegador. |
| A03 Inyeccion | Agente: aplica | [guardrails.py:112](../services/agent/guardrails.py#L112), [test briefing](../tests/security/test_briefing_injection.py) | Ataque directo bloqueado; instrucciones de documentos siguen siendo riesgo residual. | Red-team indirecto y variaciones; separar instrucciones, validar salida y permisos fuera del LLM. |
| A04 Diseno inseguro | Backend: aplica | [incidents/models.py](../services/api/incidents/models.py), [services.py](../services/api/incidents/services.py), endpoint de estado | Cierre sin confirmacion corregido; sin aislamiento tenant ni prueba de presencia humana. | SEC-03; IDs autorizados de cliente, identidad de servicio separada y aprobacion independiente. |
| A04 Diseno inseguro | Frontend: aplica | [confirmacion UI](../uis/backoffice/components/IncidentsManagerClient.tsx), [services/api.ts](../uis/backoffice/services/api.ts) | Dialogo explicito antes de resolver; cancelar no envia peticion; Playground compartido. | No confundir dialogo con autorizacion; conservar backend y no cargar PII real. |
| A04 Diseno inseguro | Agente: aplica | [MCP transition](../mcps/backend.py), [RFP approval](../data_project/pipelines/rfp_intake/approval.py) | Tools de soporte de lectura; cierre MCP bloqueado; aprobaciones RFP con digest. | Separar generacion/aprobacion/envio; nunca inventar controles de sistemas no encontrados. |
| A05 Configuracion incorrecta | Backend: aplica | [server.py:65-72](../server.py#L65), CORS `*`; [Dockerfile](../services/Dockerfile) | Catch-all critico retirado; CORS amplio, docs/reload y ejecucion root por defecto en imagen de desarrollo. | SEC-01; perfil productivo sin reload, origen explicito, usuario no-root y proxy TLS. |
| A05 Configuracion incorrecta | Frontend: aplica | [next.config.ts](../uis/backoffice/next.config.ts), [Dockerfile](../uis/Dockerfile) | No se configuran headers de seguridad en Next; imagen sin USER. Un proxy externo podria aportar headers, no verificado. | CSP, HSTS solo bajo HTTPS, frame-ancestors y despliegue no-root. |
| A05 Configuracion incorrecta | Agente: aplica | [mcps/server.py](../mcps/server.py), scopes; [Compose](../docker-compose.yml), Qdrant 6333/6334 | OAuth/scopes explicitos; puertos Qdrant publicados sin loopback, imagen latest. No se prueba acceso desde Internet. | Limitar a red privada/loopback, fijar imagen y minimizar scopes efectivos. |
| A06 Componentes vulnerables/obsoletos | Backend: aplica | [pyproject.toml](../pyproject.toml), rangos sin version exacta en varias librerias | Inventario disponible; **no se ejecuto escaneo CVE actualizado**. | SBOM y analisis de dependencias en CI; no afirmar CVEs ni ausencia de ellas. |
| A06 Componentes vulnerables/obsoletos | Frontend: aplica | [package.json](../uis/backoffice/package.json), [uis/Dockerfile](../uis/Dockerfile), `npm install` | Next/React declarados; builds de imagen no usan instalacion congelada. | Escaneo con BD actualizada y `npm ci`/lock revisado; lockfiles protegidos no modificados. |
| A06 Componentes vulnerables/obsoletos | Agente: aplica | [pyproject.toml](../pyproject.toml), LangGraph/MCP/MarkItDown | Parsers y adaptadores amplian superficie; dependencias instaladas no prueban seguridad. | Revisar avisos, fijar artefactos y aislar conversion PDF. |
| A07 Identificacion/autenticacion | Backend: aplica | [auth.py:52-95](../services/api/users/auth.py#L52), [users/routes.py](../services/api/users/routes.py) | Firma, expiracion y usuario activo comprobados; MFA/rate limiting/revocacion de JWT no acreditados. | Mantener bcrypt, limitar intentos y validar revocacion tras cambio/reset de password. |
| A07 Identificacion/autenticacion | Frontend: aplica | [middleware.ts:18-20](../uis/backoffice/middleware.ts#L18), [auth-context.tsx](../uis/backoffice/lib/auth-context.tsx) | Presencia de cookie y decode local no autentican por si solos; login JSON corregido. | Sesion verificada en servidor; no aceptar roles del navegador para permisos. |
| A07 Identificacion/autenticacion | Agente: aplica | [mcps/server.py build_app](../mcps/server.py), audiencia; [agent API](../services/agent/routes.py) | MCP usa JWT OAuth y scopes; agente usa identidad backend. Rotacion/expiracion operativa del token de servicio no probadas. | Usuarios de servicio dedicados, scopes minimos, provision y revocacion auditados. |
| A08 Integridad de software/datos | Backend: aplica | [RFP decision](../services/api/rfp_intake/routes.py), [telemetry/routes.py:78](../services/api/telemetry/routes.py#L78) | RFP contrasta digest/version; telemetria acepta lotes sin autenticacion y puede falsear metricas. | Autenticar/limitar productores, validar schema por evento y deduplicar. |
| A08 Integridad de software/datos | Frontend: aplica | [uis/Dockerfile](../uis/Dockerfile), [records proxy](../uis/backoffice/app/api/records/_shared.ts) | Instalaciones no congeladas y dataset externo mutable. | Lock verificado, dependencias confiables, esquema de respuestas y contrato de proveedor. |
| A08 Integridad de software/datos | Agente: aplica | [MemoryStore.resolve:375](../services/agent/memory.py#L375), [approval.py:30](../data_project/pipelines/rfp_intake/approval.py#L30) | Memoria requiere aprobacion y actor; aprobaciones RFP validan digest. | Mantener trazabilidad de origen; verificar contenido recuperado, no otorgarle autoridad. |
| A09 Registro/monitorizacion | Backend: aplica | [users/routes.py _send_reset_email](../services/api/users/routes.py), [telemetry](../services/api/telemetry/routes.py) | Si falta RESEND_API_KEY se imprime token/enlace de reset; no se ejecuto esa rama con cuentas reales. | Eliminar logging de tokens y PII; alertas y runbook de brechas. Riesgo pendiente. |
| A09 Registro/monitorizacion | Frontend: aplica | [services/api.ts:98](../uis/backoffice/services/api.ts#L98), warnings con payload; [backend-proxy.ts](../uis/backoffice/lib/backend-proxy.ts) | Payloads inesperados pueden acabar en consola; no se verifico pipeline de alertas. | No registrar respuestas crudas de candidatos; IDs de correlacion y redaccion. |
| A09 Registro/monitorizacion | Agente: aplica | [TraceStore](../services/agent/support.py), [_record_invocation](../mcps/server.py) | Trazas de nodos y auditoria MCP sin tokens/payloads; resumen de guardrails. | ACL por ejecucion, export protegido, alertas y retencion de trazas/checkpoints. |
| A10 SSRF | Backend: aplica | [rag.py:138-181](../data_project/pipelines/rag.py#L138), URLs de proveedores desde entorno | No URL arbitraria de request confirmada; egress configurable por operador. | Allowlist de proveedores, bloqueo de metadata y redirects, limites de salida en red. |
| A10 SSRF | Frontend: aplica al servidor Next; no aplica al HTML estatico aislado | [backend-proxy.ts](../uis/backoffice/lib/backend-proxy.ts), [records proxy](../uis/backoffice/app/api/records/_shared.ts) | Hosts de destino configurados/fijos, no un proxy de URL libre; forwarding de credenciales corregido. | Normalizar paths y limitar destino/redirects; no se confirma SSRF explotable. |
| A10 SSRF | Agente: aplica | [mcps/backend.py:138-195](../mcps/backend.py#L138), [mcp_tools.py](../services/agent/mcp_tools.py) | Paths/metodos fijados, sin redirects y con timeout en MCP; base HTTP(S) de entorno. | Controlar egress y cambios de entorno; no permitir URLs elegidas por el LLM. |

## 6. Endurecimiento: evidencia observada, no supuesta

Entorno observado: **Codespace de desarrollo**, no servidor productivo.
No se cambio ningun permiso, servicio, configuracion SSH ni regla de red.

| Control | Evidencia local del 2026-10-28 | Resultado |
| --- | --- | --- |
| Usuario no-root | `id -u` = 1000, `id -un` = codespace | Usuario actual no-root verificado. **Usuario deploy dedicado del servidor final: no verificado**. |
| Root por SSH | `/etc/ssh/sshd_config:42` contiene `PermitRootLogin yes`; linea 23 `Port 2222`; linea 12 incluye drop-ins. `sshd -T` falla: `sshd: no hostkeys available -- exiting.` | Configuracion base incompatible con prohibir root; valor efectivo no verificable con estas credenciales. No afirmar que root pueda entrar ni que este deshabilitado. |
| Permisos | `stat`: server.py 0666; services/ y data_project/ 0777; sshd_config 0644. `.env` no produjo resultado de stat: no se infiere su contenido ni presencia efectiva. | No hay separacion minima demostrada entre codigo y estado. Logs y configuracion productiva: no verificados. |
| Puertos locales | `ss -ltn`: 0.0.0.0 y :: en 2222 y 2000; resto de listeners observados en loopback. No listeners 6333/6334/5432/6379 observados en esa instantanea. | Un listener no prueba exposicion publica ni reglas de firewall; snapshot local, no servidor final. No atribuir el puerto 2000 a una app sin evidencia. |
| Firewall | `nft list ruleset`: Operation not permitted; `iptables -S`: Permission denied (must be root). | **No verificado**; no se elevo privilegio ni se modificaron reglas. |
| Contenedores | Dockerfiles backend/interfaces sin `USER`; Compose publica 8000, 3000/3001, 6333/6334 en host; backend `--reload`. | Configuracion de desarrollo no endurecida para produccion. No se arrancaron contenedores ni se comprobo runtime. |

Comandos de solo lectura ejecutados (no requieren editar configuracion):

```sh
id -u; id -un
stat -c '%a %U:%G %n' server.py services data_project /etc/ssh/sshd_config
rg -n '^(Include|PermitRootLogin|Port|PasswordAuthentication|PubkeyAuthentication|AllowUsers)' /etc/ssh/sshd_config
/usr/sbin/sshd -T
ss -ltn
nft list ruleset
iptables -S
```

Baseline **recomendado, no aplicado**: SSH por clave para usuario operativo
dedicado; `PermitRootLogin no` efectivo, privilegios minimos y sudo auditado.
Codigo no escribible por el proceso de servicio; directorios codigo 0750/archivos
0640 segun propietarios reales; logs separados 0750/0640; configuracion con
secretos 0600 y estado sensible 0700/0600. Verificar permisos de montajes,
backups y rotacion, no solo los de la imagen.

Firewall final default-deny: publicar HTTPS 443; SSH solo desde red/IP
operativa (22 o el puerto realmente autorizado); HTTP 80 solo si se justifica
por redireccion/ACME. Mantener PostgreSQL 5432, Redis 6379, Qdrant 6333/6334,
MCP 8001, backend 8000, dashboards y puertos de depuracion/modelos en red
privada o tras proxy autenticado. Estos puertos son baseline de revision,
no una afirmacion de que todos los servicios existan en este fork.
Operaciones debe aportar `sshd -T`, identidad deploy, permisos efectivos,
reglas host/cloud y prueba externa autorizada antes del sign-off.

## 7. Matriz de acciones irreversibles

| Accion requerida | Implementacion actual y evidencia | Resultado de confirmacion humana |
| --- | --- | --- |
| Rechazar automaticamente un candidato | No se encontro motor de scoring/rechazo; [tracker](../uis/backoffice/services/api.ts) modifica registros externos manualmente. | **No verificada / no implementada** para rechazo automatico. No inferir un gate a partir del CRUD. |
| Enviar propuesta comercial o contrato | [RFP decision](../services/api/rfp_intake/routes.py) exige aprobaciones/digests para documento final y protege descarga; no se encontro envio externo. | **No verificada / envio no implementado**. Aprobacion del borrador no prueba autorizacion de un envio futuro. |
| Resolver ticket con queja/datos sensibles | API exige operador, `confirm_resolution: true`, actor y transicion; UI pregunta; MCP rechaza resolver. [Prueba](../tests/security/test_operations_controls.py). | **Verificada en flujo UI/API local**, con registro de actor/fecha. No se acredita presencia humana contra clientes API maliciosos ni doble aprobacion; se requiere separar servicios/humanos. |
| Cambio masivo de estado de candidatos ATS | No se encontro tool/ruta bulk propia; hay actualizaciones individuales contra Playground. | **No verificada / bulk no encontrado**. Validar contrato externo antes de implementar. |

Las tres acciones ausentes no satisfacen una afirmacion de "las cuatro
requieren confirmacion": bloquean cualquier aprobacion que incluya habilitarlas.
Descartar incidencias o importar estados historicos no se certifica como
equivalente a una resolucion humana del ticket.

## 8. Registro de hallazgos y riesgos residuales

| ID / severidad / confianza | Evidencia e impacto | Estado | Responsable / siguiente accion |
| --- | --- | --- | --- |
| SEC-01 Critica, 10/10 | server.py base 113-126; GET arbitrario/traversal, posible exposicion de secretos y bases. | **Corregido**, canarios 200 antes, 404 despues; 7 pruebas. Despliegue de la correccion no verificado. | CTO: desplegar; investigar accesos y rotar secretos si la ruta estuvo expuesta. |
| SEC-02 Alta, 10/10 | inventory/routes.py base 42-69; POST/PUT anonimos alteraban activos. | **Corregido**: 401 anonimo, 403 user, admin/manager permitido. | Operaciones: mantener matriz de roles y token MCP operativo. |
| SEC-03 Alta, 9/10 | incidencias/API agente solo autenticaban, sin limite de rol/cliente; cierre sin confirmacion. | **Mitigado parcialmente**: rol y cierre corregidos; aislamiento por cliente/traza y pertenencia customer_id pendientes. | CTO + Soporte: modelo tenant y ACL por objeto; no usar con clientes no mutuamente autorizados. |
| SEC-04 Media, 10/10 | proxy/login backend enviaban password en query. | **Corregido**: JSON y regresiones de contrato; TLS/logs productivos pendientes. | Backend/Frontend: migrar clientes y verificar redaccion. |
| SEC-05 Alta, 10/10 | records/_shared.ts conservaba Authorization de un cliente con JWT local hacia proveedor externo. | **Corregido** en proxy: elimina Authorization y Cookie; 3 variantes probadas sin HTTP real. No se verifica si hubo fuga historica. | CTO: rotar/investigar si hubo uso real; mantener prohibicion de PII en Playground. |
| SEC-06 Media, 10/10 | sse.py difundia IDs/fecha/estado RFP entre usuarios autenticados sin filtro de propietario. | **Corregido**: canales por creador; dos pestanas propias reciben, usuario ajeno no. | Backend: preservar ACL al incorporar nuevos eventos/metadatos. |
| RES-01 Alta, observada en diseno | Incidencias sin tenant; customer_id del agente elegido por operador; Playground publico. No se comprobo PII real. | **Abierto**, requiere diseno/migracion; contencion funcional aceptada, no eliminacion del riesgo. | CTO/privacidad: tenancy, contratos, prohibir PII real hasta autorizacion. |
| RES-02 Alta si se despliega tal cual | SSH base permite root; Docker/puertos/permisos de desarrollo no endurecidos; firewall desconocido. | **Abierto / produccion no verificada**. No se altera host compartido sin autorizacion operativa. | Infraestructura: baseline y evidencia efectiva del servidor final. |
| RES-03 Media, observada en codigo | Tokens reset impresos si falta proveedor, JWT accesible a JS y warnings con payload. | **Abierto**; no se imprimieron tokens reales en esta auditoria. | Auth/Frontend: eliminar logging sensible; disenar sesiones seguras sin romper CSRF/SSR. |
| RES-04 Media, observada en codigo | Telemetria publica admite productores no autenticados, metricas falsificables y sin limites de lote especificos. | **Abierto**; no se escribieron eventos en bases reales. | Plataforma: autenticar productores y controlar cuota/esquema/idempotencia. |
| RES-05 Control no acreditado | Sin escaneo CVE actualizado, alertas/retencion integral, TLS final o evidencias legales suficientes. | **No verificado**, no es prueba de una vulnerabilidad CVE concreta. | CTO/privacidad: SBOM, escaneo CI y evidencia legal/operativa. |

No quedan criticos confirmados sin corregir en el codigo inspeccionado.
Ello no excluye vulnerabilidades en contenido excluido, servicios externos
o controles no verificados. Los residuales altos y los bloqueos de integracion
impiden el sign-off; no se pretende haber corregido toda la deuda de seguridad.

## 9. Reproduccion antes/despues del critico y validacion

Para repetir el **antes** sin checkout ni acceso a archivos reales, este
comando lee solo el codigo versionado vulnerable y crea canarios temporales:

```sh
python - <<'PY'
import ast, os, subprocess, tempfile
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.testclient import TestClient

source = subprocess.check_output(
    ["git", "show", "53a8d5f^:server.py"], text=True
)
route = next(n for n in ast.parse(source).body
             if isinstance(n, ast.AsyncFunctionDef)
             and n.name == "serve_any_other_file")
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "app"
    root.mkdir()
    (root / "private-canary.txt").write_text("SYNTHETIC_AUDIT_CANARY")
    (root.parent / "outside-canary.txt").write_text("SYNTHETIC_AUDIT_CANARY")
    app = FastAPI()
    namespace = dict(app=app, os=os, static_file_dir=str(root),
                     FileResponse=FileResponse, HTMLResponse=HTMLResponse)
    exec(compile(ast.Module(body=[route], type_ignores=[]), "audit", "exec"), namespace)
    with TestClient(app) as client:
        for path in ["/private-canary.txt", "/..%2Foutside-canary.txt"]:
            response = client.get(path)
            assert response.status_code == 200
            assert response.text == "SYNTHETIC_AUDIT_CANARY"
            print(path, response.status_code, "synthetic_canary_exposed=True")
PY
```

Para el **despues**, ejecutar `tests/security/test_static_files.py` como se
indica al principio. Verifica 404 tanto para privados como para traversal y
symlinks, conservando el indice publico. Solo SEC-01 es critico confirmado;
por tanto no se omite un antes/despues de otro critico.

Resumen de ejecuciones focalizadas (se solapan; no sumar como casos unicos):

| Comprobacion | Resultado |
| --- | --- |
| Guardrails existentes + scopes servidor MCP, baseline | 22 passed |
| Privados/traversal/symlink/indice | 7 passed |
| Operaciones + inyeccion briefing + MCP backend/servidor + inventario | 38 passed |
| Login JSON backend | 5 passed tras corregir dominio del ejemplo |
| Proxy login + cliente auth frontend | 24 passed, 2 suites |
| RFP recepcion/aprobacion + SSE aislado | 14 passed |
| Proxy publico sin credenciales | 3 passed |
| Regresion backend final focalizada conjunta | **78 passed** |
| Regresion frontend final (login, cliente auth y proxy publico) | **27 passed**, 3 suites |
| Ruff focalizado, ESLint focalizado, diff check | Aprobados; dos warnings anteriores en services/api.ts |
| Typecheck estricto del area afectada y sus imports | Aprobado con tsconfig temporal que extiende el original |
| Typecheck global | Bloqueado por los cinco errores preexistentes descritos arriba; no build global aprobado |
| Arranque integral / hardening productivo / CVEs / proveedor real | No verificados, por las limitaciones especificadas |

Comando de la regresion backend final:

```sh
PYTHON_DOTENV_DISABLED=1 SECRET_KEY=synthetic-audit-only python -m pytest \
  tests/security tests/mcps/test_backend.py tests/mcps/test_server.py \
  tests/api/test_rfp_intake_router.py tests/api/test_rfp_approval_router.py \
  tests/pipelines/test_support_agent_guardrails.py \
  services/api/inventory/tests/test_inventory_orders.py -q --disable-warnings
```

La primera ejecucion conjunta tuvo 77 aprobadas y un fallo en un fixture
antiguo que simulaba autenticacion con `object()` sin rol. Se adapto ese
fixture al rol manager real exigido por el cambio; la repeticion dio 78/78.
No se debilito el control de permisos para satisfacer la prueba.
Se validaron automaticamente las 30 entradas OWASP (tres por categoria),
todos los enlaces locales del informe y el comando exacto del canario previo.

## 10. Criterio de cierre

El informe cubre el inventario obligatorio y justifica componentes ausentes,
emplea NIST/OWASP con version, aporta 30 evaluaciones, prueba una inyeccion
neutralizada y documenta las cuatro acciones. Se corrigio el critico con
reproduccion segura antes/despues y se conservaron evidencias versionadas.

**No se cumplen aun** la verificacion efectiva SSH/firewall/usuario deploy
del servidor final, el aislamiento entre clientes ni la confirmacion de tres
acciones inexistentes. Para levantar el bloqueo: corregir/resolver residuales,
arreglar el arranque/chat y typecheck global, validar legalmente tratamiento
y proveedores, aportar evidencia de despliegue y repetir pruebas autorizadas.
No habilitar los sistemas ausentes ni usar PII real como si esta auditoria
hubiera aprobado esas capacidades.
