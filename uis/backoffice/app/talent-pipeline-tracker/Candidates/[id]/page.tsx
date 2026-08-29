import dynamic from 'next/dynamic';
import { getCandidate, getNotes } from '@/services/api';
import { notFound } from 'next/navigation';

const CandidateDetailClient = dynamic(() => import('@/components/CandidateDetailClient'), {
  loading: () => <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-400">Cargando detalles del candidato...</div>,
});

interface Props {
  params: Promise<{ id: string }>;
}

export default async function CandidateDetailPage({ params }: Props) {
  const { id } = await params;
  const candidate = await getCandidate(id).catch(() => null);

  if (!candidate) {
    notFound();
  }

  const notes = await getNotes(id).catch(() => []);

  return <CandidateDetailClient initialCandidate={candidate} initialNotes={notes} />;
}
