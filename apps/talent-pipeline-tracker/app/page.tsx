import { getCandidates } from '../services/api';
import CandidateTable from '../components/CandidateTable';
import CandidateFilters from '../components/CandidateFilters';
import Link from 'next/link';

export default async function HomePage() {
  const candidates = await getCandidates();
  // TODO: pasar filtros y búsqueda a client component
  return (
    <main className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Candidaturas — Nexova</h1>
        <Link href="/Candidates/new" className="bg-blue-600 text-white px-4 py-2 rounded">Registrar nueva</Link>
      </div>
      {/* Filtros y búsqueda aquí (client component) */}
      {/* <CandidateFilters ... /> */}
      <div className="overflow-x-auto">
        <CandidateTable candidates={candidates} />
      </div>
    </main>
  );
}
