import { Candidate, Vacancy } from "./types";

export function isValidEmail(email: string): boolean {
  const at = email.indexOf("@");
  const dot = email.lastIndexOf(".");
  return at > 0 && dot > at + 1 && dot < email.length - 1;
}

export function validateCandidate(candidate: Candidate): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (candidate.yearsOfExperience < 0 || candidate.yearsOfExperience > 50) {
    errors.push("yearsOfExperience debe ser >= 0 y <= 50");
  }
  if (candidate.currentSalary <= 0) {
    errors.push("currentSalary debe ser > 0");
  }
  if (candidate.expectedSalary <= 0) {
    errors.push("expectedSalary debe ser > 0");
  }
  if (!candidate.skills || candidate.skills.length < 1) {
    errors.push("skills debe contener al menos 1 habilidad");
  }
  if (!isValidEmail(candidate.email)) {
    errors.push("email no es válido");
  }
  if (!candidate.phone || candidate.phone.trim() === "") {
    errors.push("phone no debe estar vacío");
  }
  return { valid: errors.length === 0, errors };
}

export function validateVacancy(vacancy: Vacancy): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!vacancy.requiredSkills || vacancy.requiredSkills.length < 1) {
    errors.push("requiredSkills debe contener al menos 1 habilidad");
  }
  if (vacancy.minYearsExperience < 0) {
    errors.push("minYearsExperience debe ser >= 0");
  }
  if (vacancy.maxYearsExperience < vacancy.minYearsExperience) {
    errors.push("maxYearsExperience debe ser >= minYearsExperience");
  }
  if (vacancy.salaryRangeMin <= 0) {
    errors.push("salaryRangeMin debe ser > 0");
  }
  if (vacancy.salaryRangeMax <= 0) {
    errors.push("salaryRangeMax debe ser > 0");
  }
  if (vacancy.salaryRangeMax < vacancy.salaryRangeMin) {
    errors.push("salaryRangeMax debe ser >= salaryRangeMin");
  }
  return { valid: errors.length === 0, errors };
}
