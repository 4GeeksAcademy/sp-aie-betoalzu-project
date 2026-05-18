"use client";
import { useState } from 'react';

export default function CandidateSearch({ onSearch }: { onSearch: (q: string) => void }) {
  const [value, setValue] = useState('');
  return (
    <form onSubmit={e => { e.preventDefault(); onSearch(value); }} className="mb-4">
      <input
        type="text"
        placeholder="Buscar por nombre o email"
        value={value}
        onChange={e => setValue(e.target.value)}
        className="border rounded px-3 py-2 mr-2"
      />
      <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">Buscar</button>
    </form>
  );
}
