interface Candidate { //interface para candidatos
  id: string; // Identificador único (ej: "C-2024-0451")
  fullName: string; // Nombre completo
  email: string; // Email de contacto
  phone: string; // Teléfono de contacto
  yearsOfExperience: number; // Años totales de experiencia profesional
  skills: string[]; // Array de habilidades (ej: ["TypeScript", "React", "Node.js"])
  englishLevel: EnglishLevel; // Nivel de inglés
  seniority: SeniorityLevel; // Nivel profesional
  currentSalary: number; // Salario actual en USD
  expectedSalary: number; // Salario esperado en USD
  availability: AvailabilityStatus; // Disponibilidad actual
  location:{  // Ubicación geográfica
    country: string;
    city: string;
    zipCode: string;
    fullAddress?: string
 } 
  remoteOnly: boolean; // Solo acepta posiciones remotas
  status: CandidateStatus; // Estado actual en la base de datos
  workAuthorization: string; // Tipo de autorización de trabajo (ej: "Visa H-1B", "Permiso de trabajo europeo")
  educationLevel: string; // Nivel educativo (ej: "Bachelor's Degree in Computer Science" o certificaciones relevantes)
  preferredSchedule: preferredSchedule; // Horario preferido 
  preferredContractType: preferredContractType; // Tipo de contrato preferido
}


type EnglishLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "Nativo";
type SeniorityLevel =| "Junior" | "Semi-Senior" | "Senior" | "Lead" | "Executive";
type AvailabilityStatus = "Inmediata" | "2 semanas" | "1 mes" | "No disponible";
type CandidateStatus = "Activo" | "En proceso" | "Contratado" | "Inactivo";
type preferredSchedule = "Tiempo completo" | "Medio tiempo" | "Freelance" | "Horario flexible";
type preferredContractType = "Indefinido" | "Temporal" | "Freelance" | "Contrato por proyecto";

interface Vacancy { //interface para vacantes de empleo
  id: string; // Identificador único (ej: "V-2024-0892")
  title: string; // Título del puesto (ej: "Senior Full-Stack Developer")
  companyName: string; // Nombre de la empresa cliente
  requiredSkills: string[]; // Habilidades técnicas requeridas
  preferredSkills: string[]; // Habilidades deseables
  minYearsExperience: number; // Experiencia mínima requerida
  maxYearsExperience: number; // Experiencia máxima relevante
  requiredEnglishLevel: EnglishLevel; // Nivel mínimo de inglés
  requiredSeniority: SeniorityLevel; // Nivel de seniority requerido
  salaryRangeMin: number; // Salario mínimo ofrecido (USD)
  salaryRangeMax: number; // Salario máximo ofrecido (USD)
  isRemote: boolean; // Posición remota
  location: string; // Ubicación de oficina si no es remota
  status: VacancyStatus; // Estado actual de la vacante
  employmentType: preferredSchedule; // Tipo de empleo
  contractType: preferredContractType; // Tipo de contrato (ej: "Indefinido", "Temporal", "Freelance")
  priorityLevel: priorityLevel; // Nivel de prioridad para cubrir la vacante
} 
type priorityLevel = "Alto" | "Medio" | "Bajo";
type VacancyStatus = "abierta" | "En progreso" | "Cerrada" | "En espera";

interface SelectionProcess {
  id: string; // Identificador único (ej: "SP-2024-1523")
  candidateId: string; // Referencia al candidato
  vacancyId: string; // Referencia a la vacante
  stage: ProcessStage; // Etapa actual
  score: number; // Puntaje de match (0-100)
  notes: string; // Notas del consultor
  createdAt: Date; // Fecha de inicio del proceso
  updatedAt: Date; // Fecha de última actualización
  rejectionReason?: string; // Razón de rechazo (si aplica)
}

type ProcessStage =
  | "Screening"
  | "Interview"
  | "Technical test"
  | "final interview"
  | "Offer"
  | "Rejected"
  | "Hired";