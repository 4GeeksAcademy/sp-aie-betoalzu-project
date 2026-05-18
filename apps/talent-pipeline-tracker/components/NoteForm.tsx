"use client";
import { useState } from 'react';

export default function NoteForm({ onAdd, loading }: { onAdd: (content: string) => void, loading?: boolean }) {
  const [value, setValue] = useState('');
  return (
    <form onSubmit={e => { e.preventDefault(); onAdd(value); setValue(''); }} className="flex gap-2 mt-4">
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Añadir nota interna"
        className="border rounded px-3 py-2 flex-1"
        required
      />
      <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded" disabled={loading}>Añadir</button>
    </form>
  );
}
