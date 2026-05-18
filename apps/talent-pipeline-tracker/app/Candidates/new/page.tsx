import { CandidateForm } from '../../types/candidate';
import CandidateFormComponent from '../../components/CandidateFormComponent';
import { createCandidate } from '../../services/api';

export default function NewCandidatePage() {
  // Aquí se implementaría la lógica client-side para crear una candidatura
  // con feedback de éxito/error y validación
  return (
    <main className="container mx-auto py-8">
      <h1 className="text-2xl font-bold mb-6">Registrar nueva candidatura</h1>
      <CandidateFormComponent onSubmit={async (data: CandidateForm) => {
        await createCandidate(data);
        // Mostrar feedback y redirigir
      }} />
    </main>
  );
}
