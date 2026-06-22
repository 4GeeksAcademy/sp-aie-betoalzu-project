# Progress — Estado del Proyecto

## Estado actual
### Completado
1. Contexto de negocio definido para Nexova (problema, usuarios y criterios funcionales).
2. App Next.js de Talent Pipeline Tracker ya creada en apps/talent-pipeline-tracker.
3. Funcionalidades nucleares del frontend implementadas:
- listado de candidaturas,
- filtros por estado/etapa,
- busqueda por texto,
- detalle por candidato,
- actualizacion de datos,
- gestion de notas internas,
- alta y edicion de candidatos.
4. Integracion con API mock central mediante cliente dedicado en services/api.ts.
5. Mapeo de etiquetas legibles para status/stage en UI.

### En curso / parcialmente consolidado
1. Capa de logica TypeScript en src/utils para scoring, ranking y validaciones (hito de programacion) existe, pero no esta formalmente conectada a la app Next.js.
2. Documentacion de la app Next.js sigue en formato base de create-next-app y no refleja el alcance funcional real.

## Riesgos y brechas
1. Falta de trazabilidad de pruebas automatizadas visibles en el repo para el tracker.
2. Posible divergencia entre modelos/tipos del frontend y utilidades de dominio en src/.
3. Dependencia alta de contrato de API y de variable de entorno para ejecucion local.
4. Pendiente validar consistencia completa de idioma y labels en toda la interfaz.

## Proximos pasos previstos
1. Unificar modelo de dominio:
- definir una unica fuente de verdad para tipos Candidate/Vacancy/SelectionProcess,
- alinear src/ con apps/talent-pipeline-tracker.

2. Reforzar calidad:
- agregar tests unitarios para services/api.ts y funciones criticas de transformacion/validacion,
- agregar pruebas de flujos principales de UI.

3. Completar documentacion tecnica:
- actualizar README de la app con arquitectura real, configuracion de entorno y decisiones clave.

4. Mejorar observabilidad funcional:
- registrar errores de red/formulario y estados vacios de forma consistente.

5. Preparar siguiente iteracion AI:
- incorporar ranking/scoring de candidatos en la UI como capa incremental sobre la base ya construida.
