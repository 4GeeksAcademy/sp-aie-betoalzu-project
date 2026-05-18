import { STATUS_LABELS, STAGE_LABELS } from '../types/labels';

export function getStatusLabel(status: string) {
  return STATUS_LABELS[status] || status;
}

export function getStageLabel(stage: string) {
  return STAGE_LABELS[stage] || stage;
}
