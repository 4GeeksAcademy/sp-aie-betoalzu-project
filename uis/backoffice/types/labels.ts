// Mapeo de valores de la API a etiquetas legibles para la UI de Nexova

export const STATUS_LABELS: Record<string, string> = {
  received: 'Recibida',
  in_progress: 'En proceso',
  selected: 'Seleccionada',
  discarded: 'Descartada',
};

export const STAGE_LABELS: Record<string, string> = {
  pending: 'Pendiente de revisión',
  review: 'En revisión',
  personal_interview: 'Entrevista personal',
  technical_interview: 'Entrevista técnica',
  offer_presented: 'Oferta presentada',
};

export const INCIDENT_STATUS_LABELS: Record<string, string> = {
  open: 'Abierta',
  in_progress: 'En progreso',
  resolved: 'Resuelta',
  discarded: 'Descartada',
};

export const INCIDENT_CATEGORY_LABELS: Record<string, string> = {
  technical_failure: 'Fallo técnico',
  process_error: 'Error de proceso',
  client_complaint: 'Queja de cliente',
  candidate_issue: 'Problema de candidato',
  staff_issue: 'Incidencia de personal',
  sla_breach: 'Incumplimiento de SLA',
  data_quality: 'Calidad de datos',
  other: 'Otro',
};

export const INCIDENT_ORIGIN_LABELS: Record<string, string> = {
  customer: 'Cliente',
  branch: 'Oficina',
  internal: 'Interno',
};

export const INCIDENT_BRANCH_LABELS: Record<string, string> = {
  central: 'Central — Sede Valencia',
  valencia_operations: 'Valencia — Operaciones',
  miami_office: 'Miami Office',
  remote: 'Remoto (sin sede fija)',
};
