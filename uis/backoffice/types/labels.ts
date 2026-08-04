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
