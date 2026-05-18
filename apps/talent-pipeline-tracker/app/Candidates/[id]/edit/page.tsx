import { updateCandidate, patchCandidate, getCandidate } from '../../../services/api';
import CandidateFormComponent from '../../../components/CandidateFormComponent';
import { CandidateForm } from '../../../types/candidate';

interface Props {
  params: { id: string };
}

export default async function EditCandidatePage({ params }: Props) {
  const candidate = await getCandidate(params.id);
  return (
    <main className="container mx-auto py-8">
      <h1 className="text-2xl font-bold mb-6">Editar candidatura</h1>
      <CandidateFormComponent initial={candidate} onSubmit={async (data: CandidateForm) => {
        await updateCandidate(params.id, data);
        // Mostrar feedback y redirigir
      }} />
    </main>
  );
}
