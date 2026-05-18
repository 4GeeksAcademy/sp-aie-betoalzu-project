import { Candidate, SeniorityLevel, AvailabilityStatus, ContractType } from "./types";
// Filtra candidatos por tipo de contrato favorito
export function filterCandidatesByPreferredContractType(
  candidates: Candidate[],
  contractType: ContractType[]
): Candidate[] {
  return candidates.filter((c) =>
    c.preferredContractType ? contractType.includes(c.preferredContractType) : false
  );
}

// Filtra candidatos por horario preferido
export function filterCandidatesByPreferredSchedule(
  candidates: Candidate[],
  schedules: string[]
): Candidate[] {
  return candidates.filter((c) =>
    c.preferredSchedule ? schedules.includes(c.preferredSchedule) : false
  );
}

export function filterCandidatesBySkills(
  candidates: Candidate[],
  requiredSkills: string[]
): Candidate[] {
  const required = requiredSkills.map((s) => s.toLowerCase());
  return candidates.filter((c) =>
    required.every((skill) =>
      c.skills.some((cs) => cs.toLowerCase() === skill)
    )
  );
}

export function filterCandidatesBySeniority(
  candidates: Candidate[],
  seniority: SeniorityLevel
): Candidate[] {
  return candidates.filter((c) => c.seniority === seniority);
}

export function filterCandidatesByAvailability(
  candidates: Candidate[],
  availability: AvailabilityStatus[]
): Candidate[] {
  return candidates.filter((c) => availability.includes(c.availability));
}

export function sortCandidatesBySalary(
  candidates: Candidate[],
  order: "asc" | "desc"
): Candidate[] {
  return [...candidates].sort((a, b) =>
    order === "asc"
      ? a.expectedSalary - b.expectedSalary
      : b.expectedSalary - a.expectedSalary
  );
}

export function sortCandidatesByExperience(
  candidates: Candidate[],
  order: "asc" | "desc"
): Candidate[] {
  return [...candidates].sort((a, b) =>
    order === "asc"
      ? a.yearsOfExperience - b.yearsOfExperience
      : b.yearsOfExperience - a.yearsOfExperience
  );
}
