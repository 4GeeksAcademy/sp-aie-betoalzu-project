export type RfpTicketSummary = {
  ticket_id: string;
  rfp_id: string;
  status:
    | 'analizando'
    | 'descartado'
    | 'analisis_completo'
    | 'generando_borrador'
    | 'en-evaluación'
    | 'needs_human_review'
    | 'esperando_aprobación'
    | 'terminado';
  processing_error: string | null;
  retry_count: number;
  retry_available: boolean;
  processing: boolean;
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
  evaluation_results: {
    schema_version?: string;
    iteration_count?: number;
    section_status?: string;
    result?: {
      section_id?: string;
      draft_sha256?: string;
      overall_pass?: boolean;
      feedback_for_generator?: string;
      readability?: { pass?: boolean; score?: number; details?: string };
      relevance?: { pass?: boolean; missing_aspects?: string[] };
      compliance?: { pass?: boolean; violations?: string[]; rule_ids?: string[] };
    };
  } | null;
  approval_status: string;
  approver: string | null;
  approved_at: string | null;
};

export type RfpApprovalBranch = {
  ticket_id: string;
  department_id: string;
  thread_id: string;
  draft_sha256: string;
  draft_version: number;
  status: string;
  updated_at: string;
};

export type RfpFinalDocument = {
  ticket_id: string;
  document_format: string;
  version: number;
  sections: Array<{
    department_id: string;
    draft_content: string;
    approver: string;
    approved_at: string | null;
  }>;
  currency: string | null;
  section_digests: Record<string, string>;
  generated_at: string;
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
  approval_branches: RfpApprovalBranch[];
  approval_decisions: Array<{
    department_id: string;
    action: string;
    comment: string | null;
    approver_email: string;
    created_at: string;
  }>;
  arbitrations: Array<{
    trigger_id: string;
    departments: string[];
    arbitrator: string;
    rule: string;
    result: string;
    created_at: string;
  }>;
  final_document: RfpFinalDocument | null;
  can_approve: boolean;
  can_generate: boolean;
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
