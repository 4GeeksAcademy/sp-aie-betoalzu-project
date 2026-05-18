// Tipos e interfaces centrales para Nexova


export type EnglishLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "Nativo";
export type SeniorityLevel = "Junior" | "Semi-Senior" | "Senior" | "Lead" | "Ejecutivo";
export type AvailabilityStatus = "Inmediata" | "2 semanas" | "1 mes" | "No disponible";
export type CandidateStatus = "Activo" | "En proceso" | "Contratado" | "Inactivo";
export type VacancyStatus = "Abierta" | "En progreso" | "Cerrada" | "En espera";
export type ContractType = "Indefinido" | "Fijo discontinuo" | "Temporal" | "Cualquier contrato";
export type ProcessStage =
  | "Cribado"
  | "Entrevista"
  | "Prueba técnica"
  | "Entrevista final"
  | "Oferta"
  | "Rechazado"
  | "Contratado";

// Representa un candidato en el sistema de Nexova
export interface Candidate {
  id: string;
  fullName: string;
  email: string;
  phone: string;
  yearsOfExperience: number;
  skills: string[];
  englishLevel: EnglishLevel;
  seniority: SeniorityLevel;
  currentSalary: number;
  expectedSalary: number;
  availability: AvailabilityStatus;
  location: {
    country: string;
    city: string;
    zipCode: string;
    adress?: string;
  };
  remoteOnly: boolean;
  status: CandidateStatus;
  referredBy?: string;
  preferredContractType?: ContractType;
  preferredSchedule?: "Jornada completa" | "Jornada parcial" | "Jornada Intensiva" | "Turno Partido" | "Cualquier horario";
  }

// Representa una vacante (posición abierta) en Nexova
export interface Vacancy {
  id: string;
  title: string;
  companyName: string;
  requiredSkills: string[];
  preferredSkills: string[];
  minYearsExperience: number;
  maxYearsExperience: number;
  requiredEnglishLevel: EnglishLevel;
  requiredSeniority: SeniorityLevel;
  salaryRangeMin: number;
  salaryRangeMax: number;
  isRemote: boolean;
  location: {
    city: string;
    country: string;
  };
  status: VacancyStatus;
  benefits?: string[];
  applicationDeadline?: Date;
  contractType?: ContractType;
}

// Rastrea el progreso de un candidato en un proceso de selección
export interface SelectionProcess {
  id: string;
  candidateId: string;
  vacancyId: string;
  stage: ProcessStage;
  score: number;
  notes: string;
  createdAt: Date;
  updatedAt: Date;
  feedback?: string;
  interviewers?: string[];
}
