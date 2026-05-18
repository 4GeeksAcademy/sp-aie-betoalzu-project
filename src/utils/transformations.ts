import { Candidate, Vacancy, SeniorityLevel, CandidateStatus, SelectionProcess, ContractType } from "./types";

  let score = 0;
  // Habilidades requeridas
  const requiredSkills = vacancy.requiredSkills.map((s) => s.toLowerCase());
  const candidateSkills = candidate.skills.map((s) => s.toLowerCase());
  const hasAllRequired = requiredSkills.every((s) => candidateSkills.includes(s));
  const requiredMatchCount = requiredSkills.filter((s) => candidateSkills.includes(s)).length;
  if (hasAllRequired) score += 40;
  else if (requiredMatchCount >= Math.ceil(requiredSkills.length / 2)) score += 20;
  // Habilidades preferidas
  const preferredSkills = vacancy.preferredSkills.map((s) => s.toLowerCase());
  const preferredMatchCount = preferredSkills.filter((s) => candidateSkills.includes(s)).length;
  score += Math.min(preferredMatchCount * 10, 20);
  // Experiencia
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
  // Seniority
  if (candidate.seniority === vacancy.requiredSeniority) score += 15;
  else {
    const levels: SeniorityLevel[] = ["Junior", "Semi-Senior", "Senior", "Lead", "Ejecutivo"];
    const cIdx = levels.indexOf(candidate.seniority);
    const vIdx = levels.indexOf(vacancy.requiredSeniority);
    if (Math.abs(cIdx - vIdx) === 1) score += 7;
  }
  // Inglés
  const englishLevels: string[] = ["A1", "A2", "B1", "B2", "C1", "C2", "Nativo"];
  const cEng = englishLevels.indexOf(candidate.englishLevel);
  const vEng = englishLevels.indexOf(vacancy.requiredEnglishLevel);
  if (cEng >= vEng) score += 15;
  // Salario
  if (
    candidate.expectedSalary >= vacancy.salaryRangeMin &&
    candidate.expectedSalary <= vacancy.salaryRangeMax
  ) {
    score += 10;
  } else if (candidate.expectedSalary <= vacancy.salaryRangeMax * 1.2) {
    score += 5;
  }
  // Tipo de contrato preferido
  if (
    vacancy.preferredContractType &&
    candidate.preferredContractType &&
    vacancy.preferredContractType === candidate.preferredContractType
  ) {
    score += 5;
  }
  // Horario preferido
  if (
    vacancy.preferredSchedule &&
    candidate.preferredSchedule &&
    vacancy.preferredSchedule === candidate.preferredSchedule
  ) {
    score += 5;
  }
  return Math.min(score, 100);
}

export function rankCandidatesForVacancy(candidates: Candidate[], vacancy: Vacancy): Array<{candidate: Candidate, score: number}> {
  return candidates
    .map((c) => ({ candidate: c, score: calculateCandidateScore(c, vacancy) }))
    .sort((a, b) => b.score - a.score);
}

export function groupCandidatesBySeniority(candidates: Candidate[]): Record<SeniorityLevel, Candidate[]> {
  const result: Record<SeniorityLevel, Candidate[]> = {
    "Junior": [],
    "Semi-Senior": [],
    "Senior": [],
    "Lead": [],
    "Executive": [],
  };
  for (const c of candidates) {
    result[c.seniority].push(c);
  }
  return result;
}

export function countCandidatesByStatus(candidates: Candidate[]): Record<CandidateStatus, number> {
  return candidates.reduce((acc, c) => {
    acc[c.status] = (acc[c.status] || 0) + 1;
    return acc;
  }, {"Active":0, "In process":0, "Hired":0, "Inactive":0} as Record<CandidateStatus, number>);
}

export function calculateAverageSalary(candidates: Candidate[]): number {
  if (candidates.length === 0) return 0;
  const sum = candidates.reduce((acc, c) => acc + c.expectedSalary, 0);
  return Math.round((sum / candidates.length) * 100) / 100;
}

export function findTopSkills(candidates: Candidate[], topN: number): Array<{skill: string, count: number}> {
  const skillCount: Record<string, number> = {};
  for (const c of candidates) {
    for (const s of c.skills) {
      const key = s.toLowerCase();
      skillCount[key] = (skillCount[key] || 0) + 1;
    }
  }
  return Object.entries(skillCount)
    .map(([skill, count]) => ({ skill, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, topN);
}

export function calculateVacancyFillRate(processes: SelectionProcess[]): number {
  if (processes.length === 0) return 0;
  const hired = processes.filter((p) => p.stage === "Hired").length;
  return Math.round((hired / processes.length) * 10000) / 100;
}
