export type RfpTicketSummary = {
  ticket_id: string;
  rfp_id: string;
  status: 'analizando' | 'descartado' | 'analisis_completo';
  processing_error: string | null;
  retry_count: number;
  retry_available: boolean;
  created_at: string;
  updated_at: string;
};

export type RfpKeyAspect = {
  aspect: string;
  value: string | null;
  evidence: string;
  open_question: string | null;
};

export type RfpDepartmentSection = {
  ticket_id: string;
  department_id: string;
  key_aspects: RfpKeyAspect[];
  draft_content: string | null;
  evaluation_results: Record<string, unknown> | null;
  approval_status: string;
  approver: string | null;
  approved_at: string | null;
};

export type RfpMetadata = {
  client_name: string | null;
  client_hq: string;
  services_requested: string[];
  service_types: string[];
  scope: string | null;
  deadline: string | null;
  budget_range: string | null;
  currency: string | null;
  departments_needed: string[];
  department_extracts: Record<string, string>;
  explicitly_requests_recruitment: boolean;
  open_questions: string[];
  field_evidence: Record<string, string>;
  readability_metrics: Record<string, string | number | null>;
};

export type RfpTicketDetail = RfpTicketSummary & {
  classification: {
    is_rfp: boolean;
    reason: string;
    evidence: string;
  } | null;
  metadata: RfpMetadata | null;
  sections: RfpDepartmentSection[];
  handoff: {
    schema_version: string;
    ticket_id: string;
    active_workstreams: Array<{
      department_id: string;
      contact: string;
      key_aspects: RfpKeyAspect[];
      open_questions: string[];
    }>;
    open_questions: string[];
    summary: string;
    [key: string]: unknown;
  } | null;
};
