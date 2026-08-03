# Propuesta de Arquitectura Backend para Nexova

## 1. Objetivo del documento
Este documento propone una estructura backend para el proyecto transversal de Nexova, orientada a resolver de forma eficiente problemas operativos de multiples areas del negocio. Talent Pipeline Tracker se considera una herramienta tactica ya construida dentro de esa estrategia, no el centro de la arquitectura global.

La meta es construir una plataforma backend que permita:
- estandarizar procesos entre areas,
- conectar sistemas hoy desconectados,
- exponer contratos de API estables para diferentes productos,
- habilitar evolucion incremental hacia automatizaciones, analitica y capacidades asistidas por IA.

## 2. Contexto de negocio que condiciona la arquitectura
Nexova no parte de un problema tecnico aislado, sino de una operacion con:
- procesos manuales en seleccion,
- herramientas desconectadas,
- necesidad de trazabilidad en tiempo real,
- necesidad de escalar sin multiplicar tareas administrativas.

Por eso, la arquitectura backend debe priorizar:
1. Claridad de dominio por area de negocio (seleccion, ventas, RRHH interno, formacion, soporte).
2. Evolucion incremental (sumar modulos sin reescribir todo).
3. Contratos de API estables para frontend, sistemas legacy e integraciones futuras.
4. Observabilidad y validaciones consistentes para reducir errores operativos.

## 3. Patron arquitectonico recomendado
### Recomendacion principal
**Arquitectura en capas + modularidad por dominio (estilo Clean/Hexagonal pragmatico).**

No recomiendo MVC clasico como eje principal, porque en APIs modernas con FastAPI el valor no esta en "controladores + vistas", sino en separar:
- entrada HTTP,
- reglas de negocio,
- acceso a datos,
- contratos (schemas).

Tampoco recomiendo comenzar con serverless puro como patron central, porque:
- existen flujos operativos encadenados entre varias areas que requieren coherencia,
- el equipo necesita primero estandarizar procesos y contratos,
- introducir demasiada fragmentacion temprana puede aumentar complejidad operativa.

### Por que este patron encaja con Nexova
1. Permite resolver problemas operativos de varias areas con una misma base tecnica consistente.
2. Facilita que varios desarrolladores trabajen en paralelo por dominio sin bloquearse.
3. Mejora trazabilidad de cambios (ejemplo: ajustar reglas de seleccion o soporte sin tocar todo el sistema).
4. Deja preparada una base para integrar luego motores de scoring, recomendaciones, automatizaciones y reportes ejecutivos.

## 4. Estructura propuesta de carpetas y modulos (FastAPI)

```text
apps/
   nexova-platform-api/
    app/
      main.py
      core/
        config.py
        security.py
        logging.py
        exceptions.py
      api/
        deps.py
        router.py
        v1/
          routers/
                  recruitment.py
                  sales.py
                  hr_internal.py
                  training.py
                  support.py
                  integrations.py
            health.py
      domains/
            recruitment/
               candidates/
                  schemas.py
                  models.py
                  repository.py
                  service.py
                  validators.py
               notes/
                  schemas.py
                  models.py
                  repository.py
                  service.py
               stages/
                  schemas.py
                  service.py
            sales/
               leads/
                  schemas.py
                  repository.py
                  service.py
            hr_internal/
               onboarding/
                  schemas.py
                  repository.py
                  service.py
            training/
               enrollments/
                  schemas.py
                  repository.py
                  service.py
            support/
               tickets/
                  schemas.py
                  repository.py
                  service.py
            integrations/
               connectors/
                  service.py
      db/
        base.py
        session.py
        migrations/
      tests/
        unit/
        integration/
      scripts/
        seed.py
    pyproject.toml
    README.md
```

### Criterio de separacion
- **api/**: solo capa HTTP (routers, dependencias, versionado).
- **domains/**: logica de negocio por dominio empresarial (recruitment, sales, hr_internal, training, support, integrations).
- **db/**: infraestructura de persistencia.
- **core/**: configuracion transversal (settings, logs, errores, seguridad).

Este criterio evita mezclar reglas de negocio con detalles de transporte (HTTP) o infraestructura (DB), y reduce el acoplamiento.

Nota de alcance: dentro de `recruitment/` vive el modulo de Talent Pipeline Tracker como una capacidad concreta del dominio de seleccion.

## 5. Como influye la estructura estandar de FastAPI en esta propuesta
De la practica habitual en proyectos FastAPI, aplicaria estas convenciones:

1. **`main.py` como punto de entrada unico**
   - Inicializa app, middleware, CORS, excepciones y registro de routers.

2. **Routers por recurso/dominio**
   - Cada router define rutas de un contexto acotado.
   - Mejora legibilidad y ownership por equipo.

3. **Schemas separados de modelos de persistencia**
   - `schemas.py` para contratos de entrada/salida.
   - `models.py` para entidades de almacenamiento.
   - Esto evita exponer estructura interna de base de datos.

4. **Servicios para reglas de negocio**
   - Los routers validan/serializan; los servicios orquestan reglas.
   - Facilita pruebas unitarias sin depender de HTTP.

5. **Configuracion por entorno centralizada**
   - `core/config.py` con variables tipadas y validadas.
   - Evita inconsistencias entre local, staging y produccion.

6. **Versionado de API desde el inicio (`/api/v1`)**
   - Permite evolucion sin romper frontend existente.

## 6. Organizacion propuesta de endpoints y routers por dominio

### Base de versionado
- Prefijo comun: `/api/v1`

### Dominio: recruitment (incluye Talent Pipeline Tracker)
- `GET /api/v1/recruitment/candidates`
- `POST /api/v1/recruitment/candidates`
- `GET /api/v1/recruitment/candidates/{candidate_id}`
- `PATCH /api/v1/recruitment/candidates/{candidate_id}`
- `GET /api/v1/recruitment/candidates/{candidate_id}/notes`
- `POST /api/v1/recruitment/candidates/{candidate_id}/notes`
- `PATCH /api/v1/recruitment/candidates/{candidate_id}/stage`

Criterio: gestion completa de candidatos, seguimiento y movimiento por etapas, como submodulo del dominio de seleccion.

### Dominio: sales
- `GET /api/v1/sales/leads`
- `POST /api/v1/sales/leads`
- `PATCH /api/v1/sales/leads/{lead_id}/status`

Criterio: visibilidad y control del pipeline comercial con lenguaje de negocio unificado.

### Dominio: hr_internal
- `GET /api/v1/hr/onboarding/tasks`
- `POST /api/v1/hr/onboarding/tasks`
- `PATCH /api/v1/hr/onboarding/tasks/{task_id}`

Criterio: digitalizar flujos internos de RRHH con trazabilidad.

### Dominio: training
- `GET /api/v1/training/programs`
- `POST /api/v1/training/enrollments`
- `GET /api/v1/training/enrollments/{enrollment_id}`

Criterio: estandarizar gestion de formacion corporativa.

### Dominio: support
- `GET /api/v1/support/tickets`
- `POST /api/v1/support/tickets`
- `PATCH /api/v1/support/tickets/{ticket_id}/status`

Criterio: mejorar cumplimiento operativo y seguimiento de SLA.

### Dominio: integrations
- `POST /api/v1/integrations/crm/sync`
- `POST /api/v1/integrations/ats/sync`
- `GET /api/v1/integrations/jobs/{job_id}`

Criterio: conectar sistemas legacy y externos sin contaminar dominios de negocio.

### Dominio transversal: health
- `GET /api/v1/health`
- `GET /api/v1/ready`

Criterio: soporte a monitoreo y despliegues confiables.

## 7. Frontend y backend como sistemas separados
Aunque hoy exista monorepo, frontend y backend deben operar como sistemas desacoplados.

### Modelo de organizacion recomendado
1. **Monorepo por ahora (recomendado para esta etapa)**
   - Ventaja: velocidad de coordinacion, PRs atomicos en fase inicial.
   - Condicion: ownership claro por app y contratos explicitados.

2. **Separacion logica estricta aun dentro del monorepo**
   - Frontend en su app (`apps/talent-pipeline-tracker`).
   - Backend en su app (`apps/nexova-platform-api`).
   - Nada de imports directos del frontend al codigo interno del backend.

### Comunicacion por API
- Contrato HTTP versionado.
- Errores con formato consistente (codigo + mensaje + detalle opcional).
- Paginacion y filtros estandarizados para listas.

### Variables de entorno
- Frontend: `NEXT_PUBLIC_API_URL` apuntando al backend.
- Backend: `DATABASE_URL`, `CORS_ORIGINS`, `ENV`, `LOG_LEVEL`, etc.
- Nunca hardcodear URLs ni secretos.

### CORS
- Permitir solo origins necesarios por entorno.
- Evitar comodin `*` en produccion.
- Definir politica de metodos y headers explicita.

## 8. Decisiones tecnicas iniciales recomendadas
1. FastAPI + Pydantic v2 para validacion y serializacion.
2. SQLAlchemy 2.x + Alembic para persistencia y migraciones.
3. Pruebas: `pytest` con unitarias (servicios) e integracion (routers).
4. Logging estructurado desde inicio (JSON si es posible).
5. Manejo de errores uniforme con excepciones de dominio.
6. CI minima con lint + tests del backend en cada PR.

## 9. Riesgos y puntos de atencion
1. **Riesgo de acoplamiento entre frontend y backend**
   - Si el frontend depende de detalles internos del backend (en lugar del contrato HTTP), cualquier cambio rompe flujos.
   - Mitigacion: versionado API, schemas claros y reglas de compatibilidad.

2. **Riesgo de mezclar logica de negocio en routers**
   - Genera endpoints dificiles de testear y mantener.
   - Mitigacion: regla de equipo: routers finos, servicios con logica.

3. **Riesgo de modelar toda la empresa alrededor de una sola herramienta**
   - Si se disena el backend solo pensando en Talent Pipeline Tracker, el resto de areas volvera a crear soluciones aisladas.
   - Mitigacion: dominios empresariales explicitos desde v1 y contratos de API por contexto de negocio.

4. **Riesgo operativo por configuracion de entorno deficiente**
   - CORS, URLs o secretos mal configurados bloquean integracion o exponen seguridad.
   - Mitigacion: configuracion centralizada, checklist por entorno y validacion al arranque.

5. **Riesgo de inconsistencias entre dominios por falta de governance**
   - Si cada modulo define su propio formato de estados, errores y paginacion, la operacion pierde coherencia.
   - Mitigacion: estandares transversales de API, linters de contrato y revision arquitectonica por PR.

## 10. Plan de adopcion sugerido (corto)
1. Crear esqueleto `apps/nexova-platform-api` con estructura propuesta.
2. Implementar primero `recruitment` por impacto inmediato (incluyendo el caso Talent Pipeline Tracker).
3. Definir estandares de contrato para todos los dominios (errores, paginacion, versionado, auth).
4. Incorporar en segunda ola `sales` y `hr_internal`, segun prioridad operativa.
5. Agregar `training`, `support` e `integrations` de forma incremental con CI y observabilidad activas.

## 11. Conclusiones
Para Nexova, la mejor decision inicial no es una arquitectura "de moda", sino una plataforma backend pragmatica que reduzca friccion operativa a nivel empresa y permita evolucion por dominios. Una arquitectura en capas con modularidad empresarial, implementada con convenciones estandar de FastAPI y separacion explicita frontend/backend, ofrece el mejor balance entre velocidad de entrega, mantenibilidad y escalabilidad futura.

En este enfoque, Talent Pipeline Tracker se mantiene como una implementacion importante dentro de `recruitment`, pero la arquitectura se diseña para servir a toda la organizacion.
