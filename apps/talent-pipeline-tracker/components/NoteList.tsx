"use client";
export default function NoteList({ notes, onDelete }: { notes: { id: string, content: string, created_at: string }[], onDelete: (id: string) => void }) {
  if (notes.length === 0) {
    return <p className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">Aun no hay notas para esta candidatura.</p>;
  }

  return (
    <ul className="space-y-3">
      {notes.map(note => (
        <li key={note.id} className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-700">{note.content}</p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-xs text-slate-500">{new Date(note.created_at).toLocaleString()}</span>
            <button
              onClick={() => onDelete(note.id)}
              className="text-sm font-semibold text-red-600 transition hover:text-red-700"
            >
              Eliminar
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
