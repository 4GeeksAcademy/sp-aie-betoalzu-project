# CONTEXT — Nexova Solutions

## Resumen ejecutivo
Nexova Solutions es una consultora de recursos humanos y adquisicion de talento con sede en Valencia y expansion en Miami. Su negocio principal se apoya en operaciones de seleccion, junto con formacion corporativa y outsourcing de soporte. Aunque la empresa tiene posicion de mercado y experiencia operativa, presenta una fuerte dependencia de procesos manuales y herramientas desconectadas.

## Motivacion del proyecto
El foco principal es modernizar operaciones con mayor impacto en negocio:
- Operaciones de seleccion, por volumen, ingreso y friccion operativa.
- Tecnologia e infraestructura, por deuda tecnica y falta de integracion.

Se plantea una estrategia de IA aplicada al core del negocio, no como complemento, con capacidad de automatizar tareas repetitivas, priorizar casos, mejorar trazabilidad y acelerar decisiones.

## Contexto de negocio (H1)
Nexova opera con problemas transversales en casi todas las areas:
- Seleccion: cribado manual, seguimiento por correo y baja visibilidad del estado de candidaturas.
- Ventas: prospeccion y seguimiento poco automatizados.
- RRHH interno: procesos administrativos manuales.
- Formacion: catalogo y gestion sin plataforma robusta.
- Soporte: falta base de conocimiento y se incumplen SLA.
- Direccion: reportes tardios y sin vista integral en tiempo real.

Necesidad estrategica: evolucionar hacia una operacion conectada, medible y automatizada con datos en tiempo real.

## Contexto tecnico-funcional (H2)
Se define el desarrollo de utilidades TypeScript para el motor de candidatos y vacantes:
- Modelado de entidades: Candidate, Vacancy, SelectionProcess.
- Filtros, busquedas y ordenamientos.
- Scoring y ranking de candidatos.
- Agregaciones y reportes.
- Validaciones de reglas de negocio.

Criterios clave:
- Tipado solido y consistencia de modelos.
- Funciones puras y sin mutaciones no deseadas.
- Manejo de casos limite.
- Organizacion por responsabilidades en archivos utilitarios.

## Contexto de producto (H3)
Se requiere construir con urgencia el frontend Talent Pipeline Tracker para sustituir una hoja de calculo compartida que ya genera errores operativos.

Funcionalidades esenciales:
- Listado de candidaturas con nombre, puesto, estado y etapa.
- Filtros por estado/etapa y busqueda por nombre o email.
- Vista de detalle para actualizar estado o etapa.
- Gestion de notas internas en detalle (crear y eliminar).
- Registro y correccion de datos de candidatos.

Regla funcional critica:
- Nunca mostrar valores crudos de API en UI (por ejemplo in_progress o personal_interview).
- Mostrar siempre etiquetas legibles definidas por negocio.

## Vision de IA propuesta
Se propone evolucionar hacia un agente central para Nexova que conecte seleccion, ventas, soporte, formacion y RRHH, apoyado en datos unificados y RAG para:
- responder consultas operativas,
- sugerir acciones,
- priorizar trabajo,
- generar reportes automaticos,
- mejorar cumplimiento de SLA y calidad de decision.

## Problema que resuelve este contexto consolidado
Este documento unifica estrategia de negocio, requisitos tecnicos y objetivos funcionales para que el equipo de AI Engineering trabaje con una sola fuente de verdad al construir el sistema de pipeline de talento y su evolucion hacia capacidades avanzadas de IA.
