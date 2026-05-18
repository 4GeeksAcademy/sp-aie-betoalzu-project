"use client";
export default function NoteList({ notes, onDelete }: { notes: { id: string, content: string, created_at: string }[], onDelete: (id: string) => void }) {
  return (
    <ul className="list-disc pl-6">
      {notes.map(note => (
        <li key={note.id} className="mb-2 flex items-center justify-between">
          <span>{note.content}</span>
          <span className="ml-2 text-xs text-gray-500">({new Date(note.created_at).toLocaleString()})</span>
          <button onClick={() => onDelete(note.id)} className="ml-4 text-red-600 underline">Eliminar</button>
        </li>
      ))}
    </ul>
  );
}
