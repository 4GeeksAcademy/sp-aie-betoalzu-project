"use client";
import { useState } from 'react';

export default function CandidateSearch({ onSearch }: { onSearch: (q: string) => void }) {
  const [value, setValue] = useState('');
  return (
    <form onSubmit={e => { e.preventDefault(); onSearch(value); }} className="mb-4 flex flex-col gap-3 sm:flex-row">
      <input
        type="text"
        placeholder="Buscar por nombre o email"
        value={value}
        onChange={e => setValue(e.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
      />
      <button type="submit" className="rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark">Buscar</button>
    </form>
  );
}
