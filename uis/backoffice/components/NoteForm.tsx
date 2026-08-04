"use client";
import { useState } from 'react';

export default function NoteForm({ onAdd, loading }: { onAdd: (content: string) => void, loading?: boolean }) {
  const [value, setValue] = useState('');
  return (
    <form onSubmit={e => { e.preventDefault(); onAdd(value); setValue(''); }} className="mt-4 flex flex-col gap-3 sm:flex-row">
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Añadir nota interna"
        className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
        required
      />
      <button
        type="submit"
        className="rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-60"
        disabled={loading}
      >
        {loading ? 'Guardando...' : 'Anadir'}
      </button>
    </form>
  );
}
