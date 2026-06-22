import { getCandidate } from '../../../../services/api';
import EditCandidateFormClient from '../../../../components/EditCandidateFormClient';

interface Props {
  params: Promise<{ id: string }>;
}

export default async function EditCandidatePage({ params }: Props) {
  const { id } = await params;
  const candidate = await getCandidate(id);
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-6 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">Edicion</p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Editar candidatura</h1>
        <p className="mt-2 text-sm text-slate-600">Actualiza el perfil para mantener el seguimiento del pipeline al dia.</p>
      </section>

      <section className="surface-card p-6 sm:p-8">
        <EditCandidateFormClient candidateId={id} initialCandidate={candidate} />
      </section>
    </main>
  );
}
