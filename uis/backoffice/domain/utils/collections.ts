import { Candidate, SeniorityLevel, AvailabilityStatus, ContractType } from "../models";

export function filterCandidatesByPreferredContractType(
  candidates: Candidate[],
  contractTypes: ContractType[]
): Candidate[] {
  return candidates.filter((candidate) =>
    candidate.preferredContractType ? contractTypes.includes(candidate.preferredContractType) : false
  );
}

export function filterCandidatesByPreferredSchedule(candidates: Candidate[], schedules: string[]): Candidate[] {
  return candidates.filter((candidate) =>
    candidate.preferredSchedule ? schedules.includes(candidate.preferredSchedule) : false
  );
}

export function filterCandidatesBySkills(candidates: Candidate[], requiredSkills: string[]): Candidate[] {
  const required = requiredSkills.map((skill) => skill.toLowerCase());
  return candidates.filter((candidate) =>
    required.every((skill) => candidate.skills.some((candidateSkill) => candidateSkill.toLowerCase() === skill))
  );
}

export function filterCandidatesBySeniority(candidates: Candidate[], seniority: SeniorityLevel): Candidate[] {
  return candidates.filter((candidate) => candidate.seniority === seniority);
}

export function filterCandidatesByAvailability(
  candidates: Candidate[],
  availability: AvailabilityStatus[]
): Candidate[] {
  return candidates.filter((candidate) => availability.includes(candidate.availability));
}

export function sortCandidatesBySalary(candidates: Candidate[], order: "asc" | "desc"): Candidate[] {
  return [...candidates].sort((a, b) => (order === "asc" ? a.expectedSalary - b.expectedSalary : b.expectedSalary - a.expectedSalary));
}

export function sortCandidatesByExperience(candidates: Candidate[], order: "asc" | "desc"): Candidate[] {
  return [...candidates].sort((a, b) =>
    order === "asc" ? a.yearsOfExperience - b.yearsOfExperience : b.yearsOfExperience - a.yearsOfExperience
  );
}