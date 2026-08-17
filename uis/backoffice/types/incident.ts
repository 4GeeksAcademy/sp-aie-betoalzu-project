export const INCIDENT_STATUSES = ['open', 'in_progress', 'resolved', 'discarded'] as const;
export const INCIDENT_CATEGORIES = [
  'technical_failure',
  'process_error',
  'client_complaint',
  'candidate_issue',
  'staff_issue',
  'sla_breach',
  'data_quality',
  'other',
] as const;
export const INCIDENT_ORIGINS = ['customer', 'branch', 'internal'] as const;
export const INCIDENT_BRANCHES = ['central', 'valencia_operations', 'miami_office', 'remote'] as const;

export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];
export type IncidentCategory = (typeof INCIDENT_CATEGORIES)[number];
export type IncidentOrigin = (typeof INCIDENT_ORIGINS)[number];
export type IncidentBranch = (typeof INCIDENT_BRANCHES)[number];

export type Incident = {
  id: number;
  title: string;
  description: string | null;
  category: IncidentCategory;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  status: IncidentStatus;
  reported_by: string | null;
  assigned_to: string | null;
  ticket_id: string | null;
  created_at: string;
  updated_at: string;
};

export type IncidentInput = {
  title: string;
  description?: string | null;
  category: IncidentCategory;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  status?: IncidentStatus;
  reported_by?: string | null;
  assigned_to?: string | null;
  ticket_id?: string | null;
};

export type IncidentSummary = {
  total: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  by_branch: Record<string, number>;
  by_origin: Record<string, number>;
  open_oldest: string | null;
  open_critical_count: number;
};