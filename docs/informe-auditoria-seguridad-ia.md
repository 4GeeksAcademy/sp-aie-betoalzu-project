# Informe de auditoría de prácticas seguras en la integración de IA — Nexova

- **Fecha de ejecución:** 2026-10-30
- **Versión/commit auditado:** rama `feature/nist-security-practices`; controles implementados y verificados en el commit `fb4fc58`. Base previa auditada: `618a8e4` (spec utilizada) y `c460293` (main). El informe de ciberseguridad previo (`docs/cibersecurity-audit.md`) se audita sobre `7e42ec2`.
- **Estado global:** **NO APROBADO** para producción. Auditoría local con controles críticos corregidos y pruebas reproducibles; quedan riesgos residuales y verificaciones operativas que requieren acceso al entorno (servidor, red, firewall, tenancy) o asesoría legal. Este documento no constituye una certificación de cumplimiento legal.
- **Alcance:** sistemas de IA construidos en el fork de Nexova, conforme al briefing `docs/briefing-practicas-de-seguridad.md` y la especificación `specs/practicas-seguras-ia.md`. Solo se usaron datos sintéticos; no se consultaron datos personales reales, credenciales ni servicios de terceros.
- **Marco NIST empleado:** NIST AI RMF 1.0 (NIST AI 100-1, enero 2023) con su GenAI Profile (NIST AI 600-1, julio 2024), adaptado a los requisitos del encargo que pide las **seis funciones** del NIST CSF 2.0 (**Govern, Identify, Protect, Detect, Respond, Recover**) como estructura de evaluación — véase sección 3. No se presenta una lista genérica como evaluación: cada función tiene estado/evidencia, brechas y al menos una acción priorizada con responsable por rol y criterio de cierre.
- **Edición OWASP empleada:** OWASP Top 10 **2021** (10 categorías) evaluadas por separado para los carriles backend, frontend y sistema agéntico (sección 5).

---

## 1. Resumen ejecutivo

El encargo pedía auditar y endurecer los sistemas de IA de Nexova antes de considerarlos aptos para producción. Se confirmaron y **corrigieron en código, con prueba reproducible**, los siguientes controles:

1. **Rate limiting autenticado sobre inferencia de IA** (`/knowledge/query` y `/agent/query`): límite de ventana deslizante por usuario, respuesta **429 con cabecera `Retry-After`**, sin invocar una segunda vez al proveedor cuando se excede la cuota. Prueba: `tests/security/test_ai_controls.py`.
2. **Aislamiento de trazas del agente de soporte por operador**: la traza queda vinculada al operador autenticado que la inicia; otro operador recibe **404** y un acceso directo con actor ajeno devuelve lista vacía. Prueba en `tests/security/test_ai_controls.py`.
3. **Registro estructurado de auditoría del agente minimizado**: evento `agent_audit` con correlación, pseudónimo del actor (HMAC-SHA256 truncado a 16 hex), agente, decisión y marca de tiempo; **no incluye la pregunta del usuario** ni contenido personal. Prueba en `tests/security/test_ai_controls.py`.
4. **Corrección de umbral en recuperación RAG**: `score_threshold` pasa a usar el umbral mínimo configurado (0,5 por defecto) en lugar de una variable no definida.
5. **No se imprime el enlace/token de restablecimiento de contraseña** en ausencia de proveedor de correo; se emite un warning estructurado.

Además se **reproduce** la neutralización del caso de prompt injection del briefing (ticket de soporte) con el guardrail determinista existente, y se documentan las cuatro acciones irreversibles una por una (sección 7): solo la resolución de tickets con queja/dato sensible está **verificada** en el flujo local con confirmación humana explícita; el rechazo automático de candidatos, el envío de propuestas y la modificación masiva del ATS **no están implementados en el fork** (marcados como no implementados/no verificables, sin inferir un gate que no existe).

**Riesgos que bloquean el sign-off** (detallados en secciones 5, 6 y 9): estado del servidor/red **no verificable** (no se dispone de acceso operativo a host, firewall ni SSH); tenancy por cliente no verificado; ausencia de un motor real de scoring de CVs (el pipeline de selección "no encontrado"); verificaciones de antecedentes no confirmadas (FCRA condicional); y asuntos de gobernanza/terceros pendientes de asesoría legal.

---

## 2. Inventario de sistemas de IA

Inventario con: componente, propósito, entradas/salidas y datos, modelos/proveedores, tools/MCP, permisos, responsable interno por rol, tercero y responsabilidad compartida, riesgos y estado (presente / no encontrado / no verificable).

### 2.1 Sistemas del briefing

| # | Componente (briefing) | Qué hace | Entradas/salidas y datos | Modelos/proveedores | Tools / MCP | Permisos | Responsable interno (rol) | Tercero y responsabilidad | Riesgos principales | Estado |
|---|------------------------|----------|--------------------------|----------------------|-------------|----------|----------------------------|---------------------------|---------------------|--------|
| S1 | Pipeline de selección asistida (scoring de CVs) | Extraer datos y ranking de candidatos | Previsto: CV, historial laboral, pretensiones salariales. No se localizó motor ejecutable | — | Solo CRUD de candidatos en backoffice; sin tools de scoring | — | Responsable de Operaciones de Selección | No identificado (no implementado) | Fuga entre candidatos, sesgo no auditado, rechazo automático sin trazabilidad | **No encontrado** (solo hay CRUD frontend de candidatos: `uis/backoffice/services/api.ts`, `uis/backoffice/types/candidate.ts`) |
| S2 | RAG sobre base de candidatos | Responder "encuentra perfiles con experiencia en X" | Detectar qué fuentes se indexan; hoy el RAG comercial (S4) consulta 4 fuentes | Embeddings vía `EMBED_MODEL`/`EMBED_BASE_URL` de entorno; Qdrant | `data_project/pipelines/rag.py` (`retrieve`, `generate_answer`) | Requiere autenticación (`/knowledge/query`) y desde esta auditoría **rate limiting por usuario** | Responsable de Datos + Operaciones de Selección | Proveedor de embeddings/LLM: responsabilidad compartida (datos en tránsito no cifrados a menos que la URL sea HTTPS, ver A02) | Excessive agency: exponer datos de contacto sin control de acceso | **No encontrado/parcial** (el RAG comercial del agente de soporte existe; el RAG de candidatos sobre la base de candidatos **no está implementado**) |
| S3 | Agente de soporte primera línea (outsourcing) | Resolver tickets de clientes del servicio tercerizado | Preguntas, documentos, datos operativos; memorias por `customer_id`; checkpoints con estado de ejecución | LangGraph local; generación/embedding vía entorno; Qdrant; MCP externo | `services/agent/support.py` (tools de consulta), `services/agent/guardrails.py`, MCP | Requiere autenticación; trazas **aisladas por operador iniciador** desde esta auditoría; rate limiting por usuario | Responsable de Outsourcing/Soporte | Proveedor LLM/embeddings: responsabilidad compartida | Prompt injection (leído), cliente arbitrario, fuga entre clientes, retención de estado | **Presente** |
| S4 | Agente de prospección comercial | Redactar correos de seguimiento a prospectos | Generación de respuesta RFP con aprobación departamental; contactos de prospectos previstos | LLM vía entorno (generación RFP); RAG comercial de 4 fuentes | `data_project/pipelines/rfp_intake/approval.py` (aprobación con digest) | Separación generación/aprobación; sin envío automático verificado | Responsable de Ventas + Datos | Proveedor LLM: responsabilidad compartida | Fuga a otro cliente/prospecto en el email generado | **Parcial** (generación+aprobación encontradas; envío automático no verificado) |

### 2.2 Sistemas de IA adicionales encontrados

| Componente | Qué hace | Estado |
|------------|----------|--------|
| RAG comercial (fuente del agente de soporte) | `data_project/pipelines/rag.py`; recuperación con umbral mínimo 0,5 y generación separando instrucciones/datos | **Presente** (corregido el umbral de búsqueda en esta auditoría) |
| Pipeline RFP intake | Extracción de tickets RFP desde PDFs (MarkItDown/Qdrant) y aprobación departamental | **Presente** (los PDFs RFP se tratan como datos no confiables) |
| Servidor MCP y backend MCP | Tools de consulta de productos/incidencias con OAuth/JWT y scopes | **Presente** |
| API del agente y API de conocimiento | `/agent/*`, `/knowledge/*` expuestos por FastAPI con autenticación | **Presente** |

### 2.3 Datos sensibles y flujo

- **Clasificación:** información personal de candidatos (CV, historial laboral, pretensiones salariales), datos de empleados/clientes de outsourcing y contactos de prospectos comerciales.
- **Flujo real encontrado:** el agente de soporte recibe preguntas de operadores autenticados, aplica guardrail determinista antes de fuentes, recupera contexto de fuentes RAG/incidencias/inventario, ejecuta en LangGraph y deja trazas en SQLite. No se observó fuga entre candidatos porque el scoring de CV no existe en el fork.
- **Minimización:** el nuevo log `agent_audit` no almacena la pregunta; silencia el token de reset cuando no hay proveedor de correo.
- **Control por rol/tenant:** se aplican roles (`admin`, `manager`, `user`, operaciones); el aislamiento por tenant/customer no está verificado (ver sección 6).

---

## 3. Evaluación NIST (seis funciones)

Marco: **NIST AI RMF 1.0 (NIST AI 100-1)** + **GenAI Profile (NIST AI 600-1)** para el detalle del sistema agéntico; estructura de funciones del **NIST CSF 2.0** exigida por el encargo. Estado por función con evidencia, brecha, acción priorizada, responsable por rol y criterio de cierre.

### 3.1 Govern (Gobierno)

- **Estado/evidencia:** gobernanza documentada de sistemas de IA en `docs/cibersecurity-audit.md` y este informe; responsable interno por dominio (Soporte, Selección, Datos, Ventas); decisiones autorizadas en `memory-bank/CONTEXT.md`.
- **Brechas:** no hay política formal de uso de IA aprobada por dirección; inventario de terceros/proveedores (embeddings, LLM, Qdrant) sin contrato revisado; sin evaluación de impacto (DPIA/IA) para los sistemas encontrados; sin comité de revisión/lecciones aprendidas.
- **Acción priorizada (Alta):** aprobar una política de gobernanza de IA y un registro de terceros con responsabilidad compartida (responsable: CTO + DPO/Responsable de Protección de Datos; criterio de cierre: política aprobada, registro con contratos y DPIA para S3/S4 firmados).

### 3.2 Identify (Identificar)

- **Estado/evidencia:** inventario en sección 2, incluyendo los 4 sistemas del briefing y los adicionales hallados; flujo de datos sensibles documentado; riesgo principal de inyección identificado.
- **Brechas:** pipeline de scoring de CVs **no encontrado** (S1); RAG de candidatos no implementado (S2); no hay mapa de dependencias de terceros ni de superficie de ataque del agente (tools MCP) completo.
- **Acción priorizada (Alta):** completar el inventario de activos de IA con mapa de proveedores/tools y clasificación de datos por sistema (responsable: Arquitectura + DPO; criterio de cierre: matriz activo/dato/proveedor/riesgo actualizada y aprobada).

### 3.3 Protect (Proteger)

- **Estado/evidencia:**
  - **Rate limiting autenticado** sobre inferencia (`services/api/rate_limit.py`; dependencia en `/knowledge/query` y `/agent/query`); prueba 429 con `Retry-After` y **sin segunda invocación** al proveedor.
  - **Aislamiento de trazas** por operador (`services/agent/support.py`: tabla `support_agent_trace_owners`, `set_owner`/`is_owner`; `get_trace(actor_id=...)`).
  - **Guardrail determinista** contra inyección antes de fuentes (`services/agent/guardrails.py`), reproducido con el caso del briefing y datos sintéticos.
  - Minimización de logs de auditoría y de correo de reset.
- **Brechas:** MFA y bloqueo de intentos de login no acreditados; cifrado en reposo de las bases SQLite no verificado; ejecución no-root en producción no verificable; TLS solo si la URL del proveedor es HTTPS.
- **Acción priorizada (Crítica/alta):** endurecer autenticación (MFA, límite de intentos) y secretos en vault (responsable: CTO/Infraestructura; criterio de cierre: MFA habilitado en backoffice y claves de LLM en vault, fuera del código).

### 3.4 Detect (Detectar)

- **Estado/evidencia:** trazabilidad de nodos del agente (`TraceStore`), resumen de guardrails (`get_guardrail_summary`), registro estructurado `agent_audit` con correlación y pseudónimo (no incluye la pregunta), registro de denegaciones.
- **Brechas:** no hay alertas activas ni correlación de eventos; no hay monitoreo de derivas/falsos positivos ni métricas de sesgo; las trazas no están cifradas y su retención no está definida.
- **Acción priorizada (Alta):** definir alertas sobre hallazgo de trazas/guardrails y export protegido (responsable: Soporte + CTO/Infraestructura; criterio de cierre: dashboard/alertas con retención definida y export auditado).

### 3.5 Respond (Responder)

- **Estado/evidencia:** respuesta de denegación del guardrail y de 429; authz de trazas devuelve 404 sin exponer checkpoints; manejo de errores del agente devuelve `run_id` para investigación sin detalle interno.
- **Brechas:** no hay runbook de incidentes de IA (brecha, abuso de agente, fuga); la notificación a AEPD (72 h) no está operacionalizada; no se distinguen actores humanos/servicio.
- **Acción priorizada (Alta):** redactar runbook de respuesta y canales de notificación AEPD/FIPA (responsable: CTO + DPO; criterio de cierre: runbook aprobado con contactos y plantilla de notificación 72 h/30 días).

### 3.6 Recover (Recuperar)

- **Estado/evidencia:** base de datos del agente en SQLite local (copias bajo control del repo no acreditadas); no se verificó restauración.
- **Brechas:** sin copias de seguridad verificadas ni pruebas de restauración; sin plan de continuidad; sin proceso de lecciones aprendidas posterior a incidentes.
- **Acción priorizada (Media):** definir copias y prueba de restauración de trazas/checkpoints y bases (responsable: Infraestructura; criterio de cierre: restauración probada en entorno de pruebas al menos una vez).

---

## 4. Regulación y datos personales

### 4.1 RGPD (España/UE)

- **Base legal y finalidad:** el tratamiento de datos de candidatos/empleados previsto por S1/S2 y el de soporte (S3) debe apoyarse en una base legal válida (ej. ejecución de relación laboral/contrato, consentimiento o interés legítimo) y finalidades determinadas. No se ha verificado documentalmente.
- **Minimización:** se aplica minimización en los nuevos registros (la pregunta no se loguea; no se imprime token de reset).
- **Control de acceso:** roles verificados; separación por rol/tenant pendiente.
- **Derechos:** no se hallaron flujos de acceso/rectificación/supresión/portabilidad de datos de candidatos en el fork.
- **Evaluación de riesgos (DPIA):** pendiente para los sistemas de IA.
- **Notificación AEPD (72 h):** obligación documentada en el briefing: una brecha que suponga riesgo para los derechos y libertades debe notificarse a la AEPD en un plazo **máximo de 72 horas** desde que se tenga conocimiento. No está operacionalizado (ver Respond).
- **Art. 22 (decisiones automatizadas):** no hay rechazo automático de candidatos implementado (S1 no encontrado); antes de implementar scoring con efecto significativo debe habilitarse intervención humana, explicación y oposición.

### 4.2 FIPA (Florida, EE. UU.)

- Aplicable a operaciones en Florida (S3/S4 con datos de prospectos/clientes). La Florida Information Protection Act exige notificación en un plazo de **30 días** tras descubrir una brecha que comprometa información personal. No se ha verificado el cumplimiento operativo; queda pendiente de asesoría legal.

### 4.3 FCRA (Fair Credit Reporting Act)

- **No se da por hecho su aplicabilidad.** Aplica solo si Nexova realiza **verificaciones de antecedentes** (background checks) en procesos de selección. **No se encontró evidencia de que se realicen.** Confirmar con el responsable legal antes de tratarlo como aplicable.

### 4.4 Asuntos para asesoría legal (pendientes)

- Validar base legal y DPIA de S1–S4; contratos de proveedores (LLM/embeddings/Qdrant) y responsabilidad compartida; retención y transferencias internacionales (España↔EE. UU.); aplicabilidad real de FCRA; y designación de DPO si procede.

---

## 5. Auditoría OWASP Top 10 (2021) — matriz backend / frontend / agente

Edición: **OWASP Top 10:2021**. Estado por celda: **aplica / no aplica / no verificable**, con evidencia concreta, impacto y recomendación/corrección. No se marca como seguro lo no verificado.

| Cat. | Carril | Estado | Evidencia concreta | Impacto | Recomendación/corrección |
|------|--------|--------|--------------------|---------|--------------------------|
| A01 Broken Access Control | Backend | Aplica, con controles | Roles en `services/api/users/auth.py`; inventario requiere admin/manager para escrituras; MCP autentica GET | Riesgo de exceso de permisos | Mantener matriz de roles; añadir aislamiento por tenant |
| A01 | Frontend | Aplica, con controles | Backoffice protege rutas y llama solo a API autenticada | Exposición de UI | Revisar rutas por rol |
| A01 | Agente | Aplica, **corregido** | Trazas aisladas por operador (`support_agent_trace_owners`); otro operador → 404; prueba `tests/security/test_ai_controls.py` | Fuga de trazas a otro operador | Extender ACL por ejecución a exports y API de conocimiento |
| A02 Cryptographic Failures | Backend | No verificable | Secretos desde entorno; TLS del proveedor solo si URL HTTPS; SQLite local sin cifrado verificado | Exposición en reposo/en tránsito | Vault, cifrado de reposo, exigir HTTPS |
| A02 | Frontend | No verificable | Proxy Next.js; no se revisó cifrado de sesión | — | Revisar cabeceras TLS/HSTS |
| A02 | Agente | No verificable | `support.py`, SQLite/checkpointer; claves LLM desde entorno | Checkpoints contienen estado | Permitir solo HTTPS; retención y redacción |
| A03 Injection | Backend | Aplica, mitigado | Inputs validados por Pydantic; RAG con umbral mínimo; salida no ejecutable | Inyección SQL/comando | Serialización segura en salidas que se conviertan en SQL/comando |
| A03 | Frontend | Aplica, mitigado | Validación de formularios (`validation.js`, componentes) | XSS/CSRF | Mantener escapes; no renderizar PII |
| A03 | Agente | Aplica, **neutralizado reproducible** | Guardrail determinista `guardrails.py` bloquea antes de fuentes; caso del briefing en `tests/security/test_briefing_injection.py` | Prompt injection (leído) | Red-team indirecto/multilingüe; separar instrucciones/datos; permisos fuera del LLM |
| A04 Insecure Design | Backend | Aplica, mitigado | Confirmación de resolución de ticket; RFP con aprobación | Diseño inseguro | Revisar flujos por diseño; no habilitar gates inexistentes |
| A04 | Frontend | Aplica, con controles | Diálogo de confirmación antes de resolver; cancelar no envía | Confirmación débil vs. autorización | No confundir diálogo con autorización |
| A04 | Agente | Aplica, con controles | Transición MCP bloqueada; aprobación RFP con digest | Acciones automáticas | Separar generación/aprobación/envío |
| A05 Security Misconfiguration | Backend | No verificable | Ejecución no-root, rutas debug: sin evidencia operativa | Superficie ampliada | Desplegar no-root; sin debug en producción |
| A05 | Frontend | No verificable | Config de build/servido | — | Revisar cabeceras y modos |
| A05 | Agente | Aplica, con controles parciales | `mcps/server.py` con OAuth/scopes explícitos; **Qdrant 6333/6334 publicados** en `docker-compose.yml` sin loopback | Exposición interna | Limitar a loopback/red privada; fijar imagen Qdrant |
| A06 Vulnerable/Outdated Components | Backend | No verificable | Dependencias instaladas no auditan seguridad | — | Auditoría de deps y fijar artefactos |
| A06 | Frontend | No verificable | Node/Next deps | — | Auditoría de deps |
| A06 | Agente | Aplica | LangGraph/MCP/MarkItDown amplían superficie | Parser de PDF como vector de ataque | Revisar avisos; aislar conversión PDF |
| A07 Identification/Authentication Failures | Backend | Aplica, con límites | JWT firmado con expiración y usuario activo (`auth.py`); bcrypt | — | MFA, bloqueo de intentos, revocación tras reset |
| A07 | Frontend | Aplica, con límites | Login con JSON y proxy sin credenciales en URL | — | Idem backend |
| A07 | Agente | Aplica, con límites | MCP usa JWT OAuth/scope; agente usa identidad backend; **rate limiting por usuario añadido** | Rotación de tokens de servicio | Usuarios de servicio dedicados y scopes mínimos |
| A08 Software/Data Integrity Failures | Backend | No aplica (no se halló) | Sin deserialización de datos no confiables | — | Verificar si se introducen CI/CD |
| A08 | Frontend | No aplica (no se halló) | Paquetes de build | — | SBOM, verificación de integridad |
| A08 | Agente | Aplica | PDFs RFP y contenido externo como datos no confiables | RAG poisoning | Tratar contenido externo como no confiable (ya) y validar autoría |
| A09 Security Logging/Monitoring Failures | Backend | Parcial | No hay alertas; logs estructurados parciales | Detección lenta | Alertas, retención |
| A09 | Frontend | No verificable | Telemetría de negocio sin persistencia | — | Definir alertas |
| A09 | Agente | Aplica, **mejorado** | Trazas de nodos + `agent_audit` minimizado (correlación, pseudónimo, decisión; sin la pregunta); prueba en `tests/security/test_ai_controls.py` | Detección lenta de abuso | Alertas y retención de trazas/checkpoints |
| A10 SSRF/Server-Side Request Forgery | Backend | No aplica | Sin fetches a URL arbitrarias en backend | — | Controlar egress si se añaden integraciones |
| A10 | Frontend | No aplica | Sin requests server-side a URL arbitraria | — | — |
| A10 | Agente | Aplica, con controles | `mcps/backend.py` con paths/métodos fijados, sin redirects y timeout; URLs de entorno | SSRF si cambia entorno | Controlar egress; no permitir URLs elegidas por el LLM |

---

## 6. Baseline servidor y red

Sin acceso operativo a host/cloud/firewall durante la auditoría, por lo que:

- **Modelo SSH, login root directo, usuario deploy no-root:** **NO VERIFICABLE** en el código/repo. No se afirma que estén endurecidos.
- **Permisos que separen código/logs/configuración secreta:** NO VERIFICABLE.
- **Firewall y puertos públicos:** se observa en `docker-compose.yml` la publicación de puertos de Qdrant (6333/6334) sin loopback y del backend (8000); **no se pudo probar el acceso desde Internet**. Se recomienda limitar DB/Redis/puertos de modelo a red privada/loopback y exponer solo HTTPS (API/frontend) y SSH de operaciones.
- **Evidencia disponible:** solo entorno local Codespace de desarrollo (config no productiva). Se solicita evidencia operativa (config de host/cloud, reglas de firewall, usuario deploy) antes de declarar cualquier endurecimiento.

---

## 7. Acciones irreversibles (requieren confirmación humana)

| Acción | Flujo revisado | Prueba | Resultado confirmación humana | Estado |
|--------|----------------|--------|-------------------------------|--------|
| Descartar/rechazar candidato automáticamente | No existe motor de scoring/rechazo en el fork (S1 no encontrado); el tracker modifica registros externos manualmente | — | **No aplica / no implementado** | **No verificada / no implementada**. No se infiere un gate del CRUD. |
| Enviar propuesta comercial/contrato a prospecto | Generación RFP + aprobación con digest; **sin envío automático verificable** | `data_project/pipelines/rfp_intake/approval.py` | Separación generación/aprobación; envío no confirmado | **No verificada para envío**. No se afirma que un envío esté bloqueado sin confirmación. |
| Marcar ticket resuelto con queja/dato sensible | API exige operador, `confirm_resolution: true`, actor y transición; UI pregunta; MCP rechaza resolver | `tests/security/test_operations_controls.py` (del informe previo) | **Verificada** en flujo UI/API local con registro de actor/fecha | **Verificada (local)**. No se acredita presencia humana contra clientes API maliciosos ni doble aprobación. |
| Modificar estado de candidato en ATS masivamente | No hay ATS batch en el fork | — | — | **No verificada / no implementada** |

Nota: la verificación de resolución de tickets es local y valida el flujo API/UI con confirmación explícita; no certifica presencia humana criptográfica frente a clientes maliciosos; se recomienda separar servicios/humanos y doble aprobación para casos sensibles.

---

## 8. Pruebas reproducibles (solo datos sintéticos)

Comando (entorno de tests, `SECRET_KEY` sintética):

```bash
PYTHON_DOTENV_DISABLED=1 SECRET_KEY=synthetic-audit-only python3 -m pytest \
  tests/security/test_ai_controls.py \
  tests/security/test_briefing_injection.py \
  tests/pipelines/test_rag.py -q
```

Resultados de la sesión:

| Prueba | Resultado | Qué demuestra |
|--------|-----------|---------------|
| `test_ai_controls.py::test_rate_limit_returns_429_without_second_inference` | ✅ | 429 con `Retry-After` y **sin segunda llamada** al proveedor |
| `test_ai_controls.py::test_rate_limit_is_scoped_per_user_id` | ✅ | La cuota es por id de usuario autenticado |
| `test_ai_controls.py::test_rate_limiter_rejects_invalid_configuration` | ✅ | Rechaza límites/ventanas inválidos |
| `test_ai_controls.py::test_agent_trace_is_visible_only_to_initiating_operator` | ✅ | Operador dueño ve traza; otro operador → 404; `get_trace(actor ajeno) → []` |
| `test_ai_controls.py::test_agent_audit_log_is_structured_and_omits_question` | ✅ | Log `agent_audit` estructurado; **la pregunta (canario) no aparece** |
| `test_briefing_injection.py::test_briefing_support_injection_is_blocked_before_sources` | ✅ | Inyección del briefing bloqueada **antes de alcanzar fuentes**; sin llamadas a fuentes |
| `test_rag.py` (umbral: 2 pruebas nuevas) | ✅ | `score_threshold` usa 0,5 por defecto y 0,73 si se explicita |
| `test_rag.py` (3 pruebas de `FakeQdrantClient` preexistentes) | ⚠️ fallos preexistentes | Relacionados con el doble de Qdrant (`FakeQdrantClient` devuelve lista, no `.points`); documentados, no introducidos por esta auditoría |

Suite total en la sesión: `tests/ai_controls` + `test_briefing_injection`: todas aprobadas; RAG: 14 aprobadas / 3 preexistentes documentadas. Los datos usados en todas las pruebas son sintéticos (sin PII real, sin red externa).

---

## 9. Hallazgos priorizados

| ID | Severidad | Activo | Escenario | Impacto | Evidencia | Estado | Responsable | Corrección/mitigación | Riesgo residual |
|----|-----------|--------|-----------|---------|-----------|--------|-------------|------------------------|-----------------|
| H-01 | Crítica (heredada) | `server.py` catch-all | Lectura arbitraria de archivos sin autenticación | Compromiso de archivos/claves | Informe previo `cibersecurity-audit.md` (SEC-01) | **Corregido** en auditoría previa | CTO/Infraestructura | Catch-all retirado; 404 para rutas no registradas | Bajo (endpoints nuevos deben seguir sin catch-all) |
| H-02 | Alta | Agente de soporte, trazas | Otro operador consulta trazas ajenas | Fuga de contexto entre operadores | Nueva prueba de aislamiento | **Corregido** (commit `fb4fc58`) | Soporte/Backend | ACL por actor en `get_trace`; 404 para ajeno | Bajo |
| H-03 | Alta | `/knowledge/query`, `/agent/query` | Abuso de inferencia (costo/abuso) | Costo y abuso de modelo | Nueva prueba 429 | **Corregido** (commit `fb4fc58`) | CTO/Infraestructura | Rate limiting por usuario (429/`Retry-After`) | Medio (limiter local; gateway distribuido pendiente) |
| H-04 | Alta | Logs del agente | Log con pregunta/PII del usuario | Fuga en logs | Nueva prueba (canario ausente) | **Corregido** (commit `fb4fc58`) | Backend | Log estructurado minimizado `agent_audit` | Bajo |
| H-05 | Alta | RAG | Umbral de búsqueda no definido (fallo) | Resultados irrelevantes o fuga | Corrección `score_threshold=threshold` | **Corregido** (commit `fb4fc58`) | Datos/Backend | Usar umbral mínimo configurado | Bajo |
| H-06 | Media | Auth | Sin MFA ni bloqueo de intentos | Cuentas comprometidas | Informe previo A07 | Abierto | CTO/Infraestructura | MFA, límite de intentos, revocación tras reset | Medio |
| H-07 | Media | Servidor/red | Puertos Qdrant/backend sin loopback en Compose; SSH/firewall sin evidencia | Exposición de servicios internos | Sección 6 | **No verificable** | Infraestructura | Loopback/red privada, fijar Qdrant, evidencia operativa | Alto (sin evidencia) |
| H-08 | Media | Datos sensibles | Cifrado en reposo/en tránsito no verificado | Fuga de CVs/contactos | Sección 5 (A02) | No verificable | Infraestructura + DPO | Vault, cifrado de reposo, HTTPS obligatorio | Medio |
| H-09 | Media | Pipeline de selección | Scoring/rechazo automático **no encontrado** | Riesgo futuro (rechazo sin trazabilidad) | Sección 2 (S1) | No implementado | Operaciones de Selección + Datos | Antes de implementar: trazabilidad, intervención humana, DPIA | N/A (no existe aún) |
| H-10 | Baja/Media | Logging/monitoreo | Sin alertas activas | Detección lenta de abuso | Sección 5 (A09) | Abierto | Soporte + Infraestructura | Alertas sobre trazas/guardrails, retención definida | Medio |

---

## 10. Ruta de remediación priorizada

Orden por prioridad con esfuerzo/dependencias y **criterio verificable de cierre** para cada brecha abierta:

1. **Obtener evidencia operativa de servidor/red** (H-07): acceso SSH con usuario no-root, reglas de firewall, puertos públicos. Criterio: captura de configuración de host/cloud y firewall; `root` no accesible; DB/Redis/Qdrant no públicos. Responsable: Infraestructura.
2. **Endurecer autenticación** (H-06): MFA, bloqueo de intentos, revocación de JWT tras reset. Criterio: pruebas de login fallido repetido y de revocación. Responsable: CTO/Infraestructura.
3. **Cifrado y secretos** (H-08): mover claves LLM/embeddings a vault, exigir HTTPS, cifrar reposo (SQLite/checkpoints). Criterio: claves ausentes de código/repo; auditoría de dependencias sin fallos. Responsable: Infraestructura + DPO.
4. **Aislamiento por tenant/customer**: validar autorización de `customer_id` y separación por cliente. Criterio: prueba de dos tenant sin acceso cruzado. Responsable: Backend + Soporte.
5. **Alertas y retención** (H-10): correlación de eventos `agent_audit`/trazas/guardrails; retención definida. Criterio: alerta funcional y política de retención aprobada. Responsable: Soporte + Infraestructura.
6. **Mejoras del sistema agéntico**: usuarios de servicio dedicados y scopes mínimos MCP; aislar conversión de PDF. Criterio: scopes efectivos auditados; pipeline de PDF aislado. Responsable: CTO + Arquitectura.
7. **Gobernanza y legal** (Govern/Regulación): política de IA, registro de terceros, DPIA, notificación AEPD 72 h / FIPA 30 días operacionalizada, confirmar FCRA. Criterio: documentos aprobados por dirección y asesoría legal; runbook de notificación probado. Responsable: DPO + Dirección.
8. **Si se implementa scoring de CVs (S1/S2)**: DPIA, trazabilidad de cada decisión, intervención humana (RGPD art. 22), pruebas de sesgo. Criterio: decisión automatizada trazable y reversible. Responsable: Operaciones de Selección + Datos.

**Esfuerzo/dependencias:** items 1, 3 y 7 dependen de acceso operativo/contratos/legal; los items 2, 4, 5 y 6 son técnicos en el fork. Los hallazgos **críticos confirmados en código** (H-01) y los **altos corregibles en código** (H-02…H-05) están corregidos con prueba reproducible; no quedan críticos abiertos en código, pero la **falta de evidencia de servidor/red y tenancy bloquea el sign-off de producción**.

---

## 11. Separación de hechos, supuestos, recomendaciones y pendientes

- **Hechos verificados:** inventario real en el repo (S3/S4 y adicionales presentes; S1/S2 no encontrados); correcciones `fb4fc58` con pruebas; inyección del briefing neutralizada; resolución de tickets con confirmación explícita; Qdrant publicado en Compose.
- **Supuestos:** los cuatro sistemas del briefing son los previstos; sin motor de scoring no hay fuga de candidatos demostrable; la separación de carriles OWASP se basó en el repositorio y configuración local.
- **Recomendaciones:** las de las secciones 3, 5 y 10.
- **Pendientes:** evidencia operativa (servidor/red/firewall), tenancy, DPIA/gobernanza, asesoría legal (FCRA, base legal, transferencias), alertas/monitoreo, y confirmación de envío/propuestas y ATS batch.