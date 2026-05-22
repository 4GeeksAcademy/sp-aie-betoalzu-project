import { getCandidates } from '../services/api';
import CandidateTable from '../components/CandidateTable';
import CandidateFilters from '../components/CandidateFilters';
import Link from 'next/link';
import { STATUS_LABELS, STAGE_LABELS } from '../types/labels';

type HomePageProps = {
  searchParams?: Promise<{
    q?: string;
    status?: string;
    stage?: string;
  }>;
};

export default async function HomePage({ searchParams }: HomePageProps) {
  const resolvedSearchParams = await searchParams;
  const candidates = await getCandidates();
  const q = (resolvedSearchParams?.q || '').trim().toLowerCase();
  const status = resolvedSearchParams?.status || '';
  const stage = resolvedSearchParams?.stage || '';

  const filteredCandidates = candidates.filter((candidate) => {
    const matchesSearch =
      !q ||
      candidate.full_name.toLowerCase().includes(q) ||
      candidate.email.toLowerCase().includes(q) ||
      candidate.position.toLowerCase().includes(q);
    const matchesStatus = !status || candidate.status === status;
    const matchesStage = !stage || candidate.stage === stage;

    return matchesSearch && matchesStatus && matchesStage;
  });

  const statusOptions = Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }));
  const stageOptions = Object.entries(STAGE_LABELS).map(([value, label]) => ({ value, label }));

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-8 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
              Talento y Operaciones
            </p>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">Candidaturas Nexova</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600 sm:text-base">
              Filtra, revisa y actualiza el pipeline completo de seleccion desde un unico panel operativo.
            </p>
          </div>
          <Link
            href="/Candidates/new"
            className="inline-flex items-center justify-center rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark"
          >
            Registrar nueva
          </Link>
        </div>
      </section>

      <div className="surface-card mb-6 p-5 sm:p-6">
        <h2 className="mb-1 text-lg font-bold text-slate-900">Panel de filtros</h2>
        <p className="mb-4 text-sm text-slate-600">Acota por busqueda, estado o etapa para priorizar acciones.</p>
        <CandidateFilters stages={stageOptions} statuses={statusOptions} />
      </div>

      <div className="surface-card overflow-x-auto">
        <CandidateTable candidates={filteredCandidates} />
      </div>
    </main>
  );
}
