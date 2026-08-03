"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { CandidateForm } from '../../../types/candidate';
import CandidateFormComponent from '../../../components/CandidateFormComponent';
import { createCandidate } from '../../../services/api';

export default function NewCandidatePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(data: CandidateForm) {
    try {
      setLoading(true);
      setError(null);
      setSuccess(false);

      await createCandidate(data);
      setSuccess(true);
      router.push('/');
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo registrar la candidatura');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-6 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">Alta de candidatura</p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Registrar nueva candidatura</h1>
        <p className="mt-2 text-sm text-slate-600">Completa el perfil para incorporarlo al pipeline de seleccion.</p>
      </section>

      <section className="surface-card p-6 sm:p-8">
        <CandidateFormComponent
          onSubmit={handleSubmit}
          loading={loading}
          error={error}
          success={success}
        />
      </section>
    </main>
  );
}
