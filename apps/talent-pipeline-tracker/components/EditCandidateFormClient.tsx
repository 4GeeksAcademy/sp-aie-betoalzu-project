"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import CandidateFormComponent from './CandidateFormComponent';
import { Candidate, CandidateForm } from '../types/candidate';
import { updateCandidate } from '../services/api';

interface Props {
  candidateId: string;
  initialCandidate: Candidate;
}

export default function EditCandidateFormClient({ candidateId, initialCandidate }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(data: CandidateForm) {
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);

      await updateCandidate(candidateId, data);
      setSuccess(true);
      router.push(`/Candidates/${candidateId}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo actualizar la candidatura');
    } finally {
      setLoading(false);
    }
  }

  return (
    <CandidateFormComponent
      initial={initialCandidate}
      onSubmit={handleSubmit}
      loading={loading}
      error={error}
      success={success}
    />
  );
}
