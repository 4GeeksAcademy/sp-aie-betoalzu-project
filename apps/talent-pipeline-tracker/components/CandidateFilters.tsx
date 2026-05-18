"use client";
import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function CandidateFilters({ stages, statuses }: { stages: { value: string, label: string }[], statuses: { value: string, label: string }[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('q') || '');
  const [status, setStatus] = useState(searchParams.get('status') || '');
  const [stage, setStage] = useState(searchParams.get('stage') || '');

  function updateFilters() {
    const params = new URLSearchParams();
    if (search) params.set('q', search);
    if (status) params.set('status', status);
    if (stage) params.set('stage', stage);
    router.push('/?' + params.toString());
  }

  return (
    <form className="flex flex-wrap gap-4 mb-6" onSubmit={e => { e.preventDefault(); updateFilters(); }}>
      <input
        type="text"
        placeholder="Buscar por nombre o email"
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="border rounded px-3 py-2"
      />
      <select value={status} onChange={e => setStatus(e.target.value)} className="border rounded px-3 py-2">
        <option value="">Todos los estados</option>
        {statuses.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
      <select value={stage} onChange={e => setStage(e.target.value)} className="border rounded px-3 py-2">
        <option value="">Todas las etapas</option>
        {stages.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
      <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">Filtrar</button>
    </form>
  );
}
