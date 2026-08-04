// Tipos principales para candidaturas, notas y formularios según la API y el contexto de Nexova

export type StatusAPI = 'received' | 'in_progress' | 'selected' | 'discarded';
export type StageAPI = 'pending' | 'review' | 'personal_interview' | 'technical_interview' | 'offer_presented';

export interface Candidate {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin: string;
  cv_url: string;
  experience_years: number;
  status: StatusAPI;
  stage: StageAPI;
  applied_at: string;
}

export interface Note {
  id: string;
  content: string;
  created_at: string;
}

export interface CandidateForm {
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin: string;
  cv_url: string;
  experience_years: number;
  status: StatusAPI;
  stage: StageAPI;
}
