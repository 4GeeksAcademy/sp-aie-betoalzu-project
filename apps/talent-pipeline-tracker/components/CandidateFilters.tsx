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

  function clearFilters() {
    setSearch('');
    setStatus('');
    setStage('');
    router.push('/');
  }

  return (
    <form className="grid gap-3 md:grid-cols-2 xl:grid-cols-5" onSubmit={e => { e.preventDefault(); updateFilters(); }}>
      <input
        type="text"
        placeholder="Buscar por nombre o email"
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20 xl:col-span-2"
      />
      <select
        value={status}
        onChange={e => setStatus(e.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
      >
        <option value="">Todos los estados</option>
        {statuses.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
      <select
        value={stage}
        onChange={e => setStage(e.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
      >
        <option value="">Todas las etapas</option>
        {stages.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
      <button
        type="submit"
        className="rounded-full bg-brand px-4 py-3 text-sm font-bold text-white transition hover:bg-brand-dark"
      >
        Filtrar
      </button>
      <button
        type="button"
        onClick={clearFilters}
        className="rounded-full border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-brand hover:text-brand"
      >
        Borrar filtros
      </button>
    </form>
  );
}
