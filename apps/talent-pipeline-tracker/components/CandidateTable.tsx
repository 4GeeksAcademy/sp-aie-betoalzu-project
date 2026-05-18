import { Candidate } from '../types/candidate';
import Link from 'next/link';
import { getStatusLabel, getStageLabel } from '../utils';

export default function CandidateTable({ candidates }: { candidates: Candidate[] }) {
  return (
    <table className="min-w-full bg-white rounded shadow">
      <thead>
        <tr>
          <th className="px-4 py-2">Nombre</th>
          <th className="px-4 py-2">Puesto</th>
          <th className="px-4 py-2">Estado</th>
          <th className="px-4 py-2">Etapa</th>
          <th className="px-4 py-2">Detalle</th>
        </tr>
      </thead>
      <tbody>
        {candidates.map((c) => (
          <tr key={c.id} className="border-t">
            <td className="px-4 py-2">{c.full_name}</td>
            <td className="px-4 py-2">{c.position}</td>
            <td className="px-4 py-2">{getStatusLabel(c.status)}</td>
            <td className="px-4 py-2">{getStageLabel(c.stage)}</td>
            <td className="px-4 py-2">
              <Link href={`/Candidates/${c.id}`} className="text-blue-600 underline">Ver detalle</Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
