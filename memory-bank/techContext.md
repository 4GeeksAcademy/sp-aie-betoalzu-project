# Tech Context — Talent Pipeline Tracker

## Stack tecnologico actual
### Frontend principal
- Next.js 16 (App Router)
- React 19
- TypeScript
- Tailwind CSS 4
- ESLint 9

### Estructura relevante
- App principal: apps/talent-pipeline-tracker
- Vistas server-rendered con App Router en app/
- Componentes UI en components/
- Cliente de API en services/api.ts
- Tipado de dominio frontend en types/
- Helpers de etiquetas en utils/labels.ts

## Restricciones tecnicas identificadas
1. Backend ya definido y compartido: el frontend debe adaptarse al contrato existente de la API, no redefinirlo.
2. Valores API de status/stage no deben mostrarse crudos en UI: se traducen a etiquetas legibles.
3. Campos de formulario y detalle deben cubrir los requerimientos de la API.
4. Dependencia de variable de entorno NEXT_PUBLIC_API_URL: sin ella la app no puede operar.
5. Fetch en modo no-store para priorizar datos frescos del pipeline.

## Decisiones de arquitectura tomadas
1. Separacion por capas simple y mantenible:
- Capa de acceso a datos en services/api.ts (fetch, manejo de errores, normalizacion).
- Capa de presentacion en componentes y paginas de Next.js.
- Capa de tipado en types/.

2. Normalizacion de payload API para tolerancia a variaciones:
- Se acepta linkedin o linkedin_url y se unifica en linkedin en cliente.
- Se soportan respuestas en formatos array, results o data para listas.

3. Filtrado en frontend para UX inmediata:
- Busqueda por nombre/email/posicion y filtros por estado/etapa sin recarga completa visible para usuario.

4. Server Components para carga inicial:
- Las paginas obtienen datos en servidor para entregar vista inicial consistente.

5. Modularidad para evolucion futura:
- Tipos y labels centralizados para facilitar escalado a nuevas vistas, validaciones y automatizaciones.

## Estado tecnico complementario (hito de programacion en src/)
Existe una base de utilidades TypeScript en src/ (colecciones, busqueda, transformaciones y validaciones) orientada al motor de scoring y matching del dominio Nexova. Esta capa no esta integrada directamente con la app Next.js actual y requiere consolidacion para convertirse en libreria productiva reutilizable.
