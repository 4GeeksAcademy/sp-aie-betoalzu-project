# RFP intake: API y contrato de handoff v1

La Parte 1 conserva la fuente de verdad en PostgreSQL mediante las tablas
`rfp_intake_tickets`, `rfp_intake_metadata`, `rfp_intake_department_sections` y
`rfp_intake_handoffs`. El PDF original y el Markdown convertido son artefactos
de proceso: se guardan en `data_project/raw/rfp_intake/` y
`data_project/process/rfp_intake/`, respectivamente, y no sustituyen esos
registros.

## API autenticada

- `POST /rfp-intake/tickets`: recibe el campo multipart `file`; acepta PDF de
  hasta 20 MiB y devuelve HTTP 202 con el ticket en `analizando`.
- `GET /rfp-intake/tickets`: lista los últimos 100 tickets del usuario.
- `GET /rfp-intake/tickets/{ticket_id}`: devuelve el estado, errores
  recuperables, clasificación y resultado persistido.
- `POST /rfp-intake/tickets/{ticket_id}/retry`: reintenta un fallo técnico
  manteniendo el mismo ticket y el mismo archivo.

La carga y consulta están limitadas al usuario que creó el ticket. Los fallos
técnicos no se convierten en `descartado`: se conservan en `processing_error`
y habilitan un reintento. Una ejecución marcada como activa y sin progreso
durante 20 minutos se considera interrumpida. El inicio de FastAPI también
recupera tickets interrumpidos. La clasificación de negocio inválida termina
en `descartado`; el resultado válido solo llega a `analisis_completo` después
de guardar metadatos, secciones y handoff en una transacción.

## Handoff versionado

`schema_version` identifica el contrato; consumidores deben rechazar o
adaptarse explícitamente a versiones que no soporten. El payload v1 tiene esta
forma:

```json
{
  "schema_version": "1.0",
  "ticket_id": "uuid",
  "metadata": {
    "client_name": "Nombre o null",
    "client_hq": "España | Miami | no_especificado",
    "services_requested": [],
    "service_types": [],
    "scope": null,
    "deadline": null,
    "budget_range": null,
    "currency": "EUR | USD | null",
    "departments_needed": [],
    "open_questions": [],
    "field_evidence": {},
    "readability_metrics": {}
  },
  "active_workstreams": [
    {
      "department_id": "seleccion | capacitacion | soporte",
      "contact": "Responsable del briefing",
      "key_aspects": [],
      "open_questions": []
    }
  ],
  "key_aspects": {
    "seleccion": [],
    "capacitacion": [],
    "soporte": []
  },
  "open_questions": [],
  "summary": "Resumen accionable para Ventas",
  "created_at": "fecha ISO-8601"
}
```

Solo aparecen workstreams activados por servicios con evidencia. El handoff
guarda hechos y preguntas abiertas, con responsable por departamento, para que
la Parte 2 pueda continuar sin abrir ni volver a analizar el PDF. La Parte 1
no genera precios, borradores, evaluaciones, aprobaciones ni documento final.
