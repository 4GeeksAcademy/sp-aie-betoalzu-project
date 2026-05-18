import { getCandidate, getNotes } from '../../../services/api';
import { getStatusLabel, getStageLabel } from '../../../utils';
import Link from 'next/link';
import { notFound } from 'next/navigation';

interface Props {
  params: { id: string };
}

export default async function CandidateDetailPage({ params }: Props) {
  try {
    const candidate = await getCandidate(params.id);
    const notes = await getNotes(params.id);
    return (
      <main className="container mx-auto py-8">
        <Link href="/" className="text-blue-600 underline mb-4 inline-block">← Volver al listado</Link>
        <h1 className="text-2xl font-bold mb-4">Detalle de candidatura</h1>
        <section className="bg-white rounded shadow p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><strong>Nombre:</strong> {candidate.full_name}</div>
            <div><strong>Email:</strong> {candidate.email}</div>
            <div><strong>Teléfono:</strong> {candidate.phone}</div>
            <div><strong>Puesto:</strong> {candidate.position}</div>
            <div><strong>LinkedIn:</strong> <a href={candidate.linkedin} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">Perfil</a></div>
            <div><strong>CV:</strong> <a href={candidate.cv_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">Ver CV</a></div>
            <div><strong>Años de experiencia:</strong> {candidate.experience_years}</div>
            <div><strong>Estado:</strong> {getStatusLabel(candidate.status)}</div>
            <div><strong>Etapa:</strong> {getStageLabel(candidate.stage)}</div>
            <div><strong>Fecha de aplicación:</strong> {new Date(candidate.applied_at).toLocaleDateString()}</div>
          </div>
        </section>
        <section className="bg-white rounded shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-2">Notas internas</h2>
          <ul className="list-disc pl-6">
            {notes.map((note: any) => (
              <li key={note.id} className="mb-2">
                <span>{note.content}</span>
                <span className="ml-2 text-xs text-gray-500">({new Date(note.created_at).toLocaleString()})</span>
                {/* Botón para eliminar nota aquí */}
              </li>
            ))}
          </ul>
          {/* Formulario para añadir nota aquí */}
        </section>
        {/* Controles para actualizar estado y etapa aquí */}
        {/* Formulario para editar candidatura aquí */}
      </main>
    );
  } catch {
    notFound();
  }
}
