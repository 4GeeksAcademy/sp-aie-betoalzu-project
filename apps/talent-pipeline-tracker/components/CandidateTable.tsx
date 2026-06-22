import { Candidate } from '../types/candidate';
import Link from 'next/link';
import { getStatusLabel, getStageLabel } from '../utils';

export default function CandidateTable({ candidates }: { candidates: Candidate[] }) {
  return (
    <table className="min-w-full text-sm">
      <thead className="bg-slate-50">
        <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
          <th className="px-5 py-3 font-semibold">Nombre</th>
          <th className="px-5 py-3 font-semibold">Puesto</th>
          <th className="px-5 py-3 font-semibold">Estado</th>
          <th className="px-5 py-3 font-semibold">Etapa</th>
          <th className="px-5 py-3 font-semibold">Detalle</th>
        </tr>
      </thead>
      <tbody>
        {candidates.length === 0 && (
          <tr>
            <td className="px-5 py-10 text-center text-slate-500" colSpan={5}>
              No se encontraron aspirantes con los filtros aplicados.
            </td>
          </tr>
        )}
        {candidates.map((c) => (
          <tr key={c.id} className="border-t border-slate-200 text-slate-700 transition hover:bg-brand/5">
            <td className="px-5 py-4 font-semibold text-slate-900">{c.full_name}</td>
            <td className="px-5 py-4">{c.position}</td>
            <td className="px-5 py-4">{getStatusLabel(c.status)}</td>
            <td className="px-5 py-4">{getStageLabel(c.stage)}</td>
            <td className="px-5 py-4">
              <Link href={`/Candidates/${c.id}`} className="font-semibold text-brand transition hover:text-brand-dark">
                Ver detalle
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
