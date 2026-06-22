# Skill: Candidate Data Quality Guard

## Proposito
Prevenir que entren o se actualicen candidaturas con datos inconsistentes, incompletos o fuera de reglas de negocio, antes de aprobar cambios en UI o capa de API.

## Cuando usar esta skill
- En PRs que modifiquen formularios de alta/edicion de candidatos.
- En cambios de tipos de dominio o validaciones de datos.
- En cambios del cliente API que afecten parsing, normalizacion o payloads.

## Objetivo operativo
1. Verificar integridad minima de datos en creacion y edicion de candidatos.
2. Detectar validaciones faltantes o inconsistentes entre UI, tipos y API.
3. Confirmar mensajes de error claros y accionables para usuario.
4. Bloquear aprobacion de PR si se permite persistir datos invalidos.

## Inputs requeridos
1. Formularios y flujos de edicion:
   - `apps/talent-pipeline-tracker/components/CandidateFormComponent.tsx`
   - `apps/talent-pipeline-tracker/components/EditCandidateFormClient.tsx`
2. Tipado de dominio:
   - `apps/talent-pipeline-tracker/types/candidate.ts`
3. Capa de acceso a API:
   - `apps/talent-pipeline-tracker/services/api.ts`
4. Utilidades de validacion de dominio (si aplica):
   - `src/utils/validations.ts`
5. Diff del PR o lista de archivos modificados.

## Reglas obligatorias
1. Campos requeridos no pueden enviarse vacios o con solo espacios.
2. `email` debe cumplir formato valido y conservar consistencia al editar.
3. `linkedin` y `cv_url` deben ser URLs validas y seguras (`http` o `https`).
4. `experience_years` debe ser numero, no negativo y en rango razonable.
5. `status` y `stage` deben ser valores permitidos por tipos del dominio.
6. El sistema debe mostrar errores legibles al usuario cuando la validacion falle.
7. No se permite guardar candidatura si hay errores de validacion en cliente.

## Procedimiento de verificacion
1. Revisar validaciones en submit del formulario de alta y edicion.
2. Revisar tipos y coerciones para evitar envio de datos corruptos.
3. Revisar manejo de errores de API y visualizacion en UI.
4. Buscar rutas de guardado alternativas que omitan validaciones.
5. Confirmar coherencia entre tipos de dominio, formularios y payload API.
6. Verificar casos limite:
   - email invalido
   - URL invalida
   - experiencia negativa
   - campos obligatorios vacios

## Criterios de verificacion (PASS/FAIL)
### PASS
- No se puede enviar candidatura con datos invalidos.
- Validaciones son consistentes entre alta y edicion.
- Tipos y payloads previenen valores fuera de contrato.
- Errores de validacion se muestran de forma clara en la UI.
- Casos limite relevantes quedan cubiertos por pruebas o checks manuales documentados.

### FAIL
- El formulario permite guardar datos invalidos o incompletos.
- Hay discrepancias entre reglas de alta y reglas de edicion.
- Se envian datos sin validar o mal tipados a la API.
- Errores solo se registran en consola sin feedback al usuario.
- No hay evidencia de verificacion en escenarios limite criticos.

## Formato de salida recomendado
- `resultado`: PASS | FAIL
- `riesgo`: alto | medio | bajo
- `hallazgos`: lista con archivo, evidencia y regla incumplida
- `acciones_requeridas`: cambios minimos para cumplir regla
- `bloquea_pr`: true | false

## Plantilla de hallazgo
- `severidad`: alta | media | baja
- `archivo`: <ruta>
- `evidencia`: <linea o snippet>
- `regla`: <numero de regla>
- `impacto`: <como afecta calidad de datos o operacion>
- `correccion`: <cambio puntual recomendado>

## Criterio de bloqueo
Un PR no puede aprobarse si permite crear o actualizar candidaturas con datos invalidos en campos criticos (`email`, `linkedin`, `cv_url`, `experience_years`, `status`, `stage`).
