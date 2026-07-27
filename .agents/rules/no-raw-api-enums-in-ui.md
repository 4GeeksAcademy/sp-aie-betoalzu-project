# Regla: no-raw-api-enums-in-ui

## Objetivo
Evitar que la interfaz muestre valores crudos del backend para status y stage, y garantizar etiquetas legibles para negocio.

## Alcance
Aplica a todo codigo de UI en:
- apps/talent-pipeline-tracker/app
- apps/talent-pipeline-tracker/components

## Reglas obligatorias
1. Todo status o stage visible en UI debe pasar por mapeadores centralizados de labels.
2. Esta prohibido hardcodear enums de API en JSX o TSX.
3. Si llega un valor no reconocido, se debe mostrar una etiqueta segura (por ejemplo, Desconocido) y registrar warning.
4. Cualquier nuevo enum de API requiere actualizar labels y su prueba asociada antes de merge.

## Fuente de verdad actual
- apps/talent-pipeline-tracker/utils/labels.ts

## Checklist de revision
1. Buscar enums crudos en componentes y paginas de UI.
2. Verificar uso de utilidades de labels centralizadas.
3. Confirmar fallback para valores no mapeados.
4. Validar visualmente listado y detalle de candidato.

## Criterio de bloqueo
Un PR no puede aprobarse si renderiza valores crudos de API en pantalla para status o stage.
