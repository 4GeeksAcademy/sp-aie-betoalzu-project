import { Candidate } from "./types";

export function findCandidateById(candidates: Candidate[], id: string): Candidate | null {
  return candidates.find((c) => c.id === id) || null;
}

export function findCandidateByEmail(candidates: Candidate[], email: string): Candidate | null {
  const target = email.toLowerCase();
  return candidates.find((c) => c.email.toLowerCase() === target) || null;
}

export function binarySearchCandidateBySalary(sortedCandidates: Candidate[], targetSalary: number): number {
  let left = 0;
  let right = sortedCandidates.length - 1;
  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const salary = sortedCandidates[mid].expectedSalary;
    if (salary === targetSalary) return mid;
    if (salary < targetSalary) left = mid + 1;
    else right = mid - 1;
  }
  return -1;
}
