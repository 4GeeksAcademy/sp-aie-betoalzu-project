import { getCandidate, getNotes } from '../../../services/api';
import CandidateDetailClient from '../../../components/CandidateDetailClient';
import { notFound } from 'next/navigation';

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
