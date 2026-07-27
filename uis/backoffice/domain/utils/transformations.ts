import { Candidate, Vacancy, SeniorityLevel, CandidateStatus, SelectionProcess } from "../models";

export function calculateCandidateScore(candidate: Candidate, vacancy: Vacancy): number {
  let score = 0;

  const requiredSkills = vacancy.requiredSkills.map((skill) => skill.toLowerCase());
  const candidateSkills = candidate.skills.map((skill) => skill.toLowerCase());
  const hasAllRequired = requiredSkills.every((skill) => candidateSkills.includes(skill));
  const requiredMatchCount = requiredSkills.filter((skill) => candidateSkills.includes(skill)).length;

  if (hasAllRequired) {
    score += 40;
  } else if (requiredMatchCount >= Math.ceil(requiredSkills.length / 2)) {
    score += 20;
  }

  const preferredSkills = vacancy.preferredSkills.map((skill) => skill.toLowerCase());
  const preferredMatchCount = preferredSkills.filter((skill) => candidateSkills.includes(skill)).length;
  score += Math.min(preferredMatchCount * 10, 20);

  if (
    candidate.yearsOfExperience >= vacancy.minYearsExperience &&
    candidate.yearsOfExperience <= vacancy.maxYearsExperience
  ) {
    score += 20;
  } else if (
    candidate.yearsOfExperience >= vacancy.minYearsExperience - 2 &&
    candidate.yearsOfExperience <= vacancy.maxYearsExperience + 2
  ) {
    score += 10;
  }

  if (candidate.seniority === vacancy.requiredSeniority) {
    score += 15;
  } else {
    const levels: SeniorityLevel[] = ["Junior", "Semi-Senior", "Senior", "Lead", "Ejecutivo"];
    const candidateIndex = levels.indexOf(candidate.seniority);
    const vacancyIndex = levels.indexOf(vacancy.requiredSeniority);
    if (Math.abs(candidateIndex - vacancyIndex) === 1) {
      score += 7;
    }
  }

  const englishLevels = ["A1", "A2", "B1", "B2", "C1", "C2", "Nativo"];
  const candidateEnglishIndex = englishLevels.indexOf(candidate.englishLevel);
  const vacancyEnglishIndex = englishLevels.indexOf(vacancy.requiredEnglishLevel);
  if (candidateEnglishIndex >= vacancyEnglishIndex) {
    score += 15;
  }

  if (candidate.expectedSalary >= vacancy.salaryRangeMin && candidate.expectedSalary <= vacancy.salaryRangeMax) {
    score += 10;
  } else if (candidate.expectedSalary <= vacancy.salaryRangeMax * 1.2) {
    score += 5;
  }

  if (
    vacancy.preferredContractType &&
    candidate.preferredContractType &&
    vacancy.preferredContractType === candidate.preferredContractType
  ) {
    score += 5;
  }

  if (vacancy.preferredSchedule && candidate.preferredSchedule && vacancy.preferredSchedule === candidate.preferredSchedule) {
    score += 5;
  }

  return Math.min(score, 100);
}

export function rankCandidatesForVacancy(
  candidates: Candidate[],
  vacancy: Vacancy
): Array<{ candidate: Candidate; score: number }> {
  return candidates
    .map((candidate) => ({ candidate, score: calculateCandidateScore(candidate, vacancy) }))
    .sort((a, b) => b.score - a.score);
}

export function groupCandidatesBySeniority(candidates: Candidate[]): Record<SeniorityLevel, Candidate[]> {
  const result: Record<SeniorityLevel, Candidate[]> = {
    Junior: [],
    "Semi-Senior": [],
    Senior: [],
    Lead: [],
    Ejecutivo: [],
  };

  for (const candidate of candidates) {
    result[candidate.seniority].push(candidate);
  }

  return result;
}

export function countCandidatesByStatus(candidates: Candidate[]): Record<CandidateStatus, number> {
  const initial: Record<CandidateStatus, number> = {
    Activo: 0,
    "En proceso": 0,
    Contratado: 0,
    Inactivo: 0,
  };

  return candidates.reduce((accumulator, candidate) => {
    accumulator[candidate.status] += 1;
    return accumulator;
  }, initial);
}

export function calculateAverageSalary(candidates: Candidate[]): number {
  if (candidates.length === 0) {
    return 0;
  }

  const sum = candidates.reduce((accumulator, candidate) => accumulator + candidate.expectedSalary, 0);
  return Math.round((sum / candidates.length) * 100) / 100;
}

export function findTopSkills(candidates: Candidate[], topN: number): Array<{ skill: string; count: number }> {
  const skillCount: Record<string, number> = {};

  for (const candidate of candidates) {
    for (const skill of candidate.skills) {
      const key = skill.toLowerCase();
      skillCount[key] = (skillCount[key] || 0) + 1;
    }
  }

  return Object.entries(skillCount)
    .map(([skill, count]) => ({ skill, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, topN);
}

export function calculateVacancyFillRate(processes: SelectionProcess[]): number {
  if (processes.length === 0) {
    return 0;
  }

  const hired = processes.filter((process) => process.stage === "Contratado").length;
  return Math.round((hired / processes.length) * 10000) / 100;
}