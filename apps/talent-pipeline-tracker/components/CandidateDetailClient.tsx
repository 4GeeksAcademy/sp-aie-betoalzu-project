"use client";

import Link from 'next/link';
import { useState } from 'react';
import { addNote, deleteNote, patchCandidate } from '../services/api';
import NoteForm from './NoteForm';
import NoteList from './NoteList';
import { Candidate, Note, StageAPI, StatusAPI } from '../types/candidate';
import { getStageLabel, getStatusLabel } from '../utils';
import { STAGE_LABELS, STATUS_LABELS } from '../types/labels';

interface Props {
  initialCandidate: Candidate;
  initialNotes: Note[];
}

export default function CandidateDetailClient({ initialCandidate, initialNotes }: Props) {
  const [candidate, setCandidate] = useState(initialCandidate);
  const [notes, setNotes] = useState(initialNotes);
  const [status, setStatus] = useState<StatusAPI>(initialCandidate.status);
  const [stage, setStage] = useState<StageAPI>(initialCandidate.stage);
  const [savingStatus, setSavingStatus] = useState(false);
  const [addingNote, setAddingNote] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handlePatchStatusAndStage() {
    setSavingStatus(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await patchCandidate(candidate.id, { status, stage });
      setCandidate(updated);
      setSuccess('Estado y etapa actualizados correctamente.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo actualizar estado y etapa.');
    } finally {
      setSavingStatus(false);
    }
  }

  async function handleAddNote(content: string) {
    setAddingNote(true);
    setError(null);
    setSuccess(null);
    try {
      const createdNote = await addNote(candidate.id, content);
      setNotes((prev) => [createdNote, ...prev]);
      setSuccess('Nota añadida correctamente.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo añadir la nota.');
    } finally {
      setAddingNote(false);
    }
  }

  async function handleDeleteNote(noteId: string) {
    setError(null);
    setSuccess(null);
    try {
      await deleteNote(candidate.id, noteId);
      setNotes((prev) => prev.filter((note) => note.id !== noteId));
      setSuccess('Nota eliminada correctamente.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar la nota.');
    }
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <Link
        href="/"
        className="mb-4 inline-flex rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-brand hover:text-brand"
      >
        Volver al listado
      </Link>
      <h1 className="mb-4 text-3xl font-extrabold tracking-tight text-slate-900">Detalle de candidatura</h1>

      {(error || success) && (
        <div className="mb-4" role="status" aria-live="polite">
          {error && <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</p>}
          {success && <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">{success}</p>}
        </div>
      )}

      <section className="surface-card mb-6 p-6">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-slate-900">{candidate.full_name}</h2>
            <p className="text-sm text-slate-600">{candidate.position}</p>
          </div>
          <Link
            href={`/Candidates/${candidate.id}/edit`}
            className="rounded-full bg-brand px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-dark"
          >
            Editar candidatura
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-4 text-sm text-slate-700 md:grid-cols-2">
          <div><strong>Email:</strong> {candidate.email}</div>
          <div><strong>Telefono:</strong> {candidate.phone}</div>
          <div>
            <strong>LinkedIn:</strong>{' '}
            <a href={candidate.linkedin} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand transition hover:text-brand-dark">
              Perfil
            </a>
          </div>
          <div>
            <strong>CV:</strong>{' '}
            <a href={candidate.cv_url} target="_blank" rel="noopener noreferrer" className="font-semibold text-brand transition hover:text-brand-dark">
              Ver CV
            </a>
          </div>
          <div><strong>Anos de experiencia:</strong> {candidate.experience_years}</div>
          <div><strong>Estado:</strong> {getStatusLabel(candidate.status)}</div>
          <div><strong>Etapa:</strong> {getStageLabel(candidate.stage)}</div>
          <div><strong>Fecha de aplicacion:</strong> {new Date(candidate.applied_at).toLocaleDateString()}</div>
        </div>
      </section>

      <section className="surface-card mb-6 p-6">
        <h2 className="mb-4 text-xl font-bold text-slate-900">Actualizar estado y etapa</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-2">
            <span className="text-sm font-semibold text-slate-700">Estado</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as StatusAPI)}
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-semibold text-slate-700">Etapa</span>
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value as StageAPI)}
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
            >
              {Object.entries(STAGE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={handlePatchStatusAndStage}
          className="mt-4 rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-60"
          disabled={savingStatus}
        >
          {savingStatus ? 'Actualizando...' : 'Guardar cambios'}
        </button>
      </section>

      <section className="surface-card mb-6 p-6">
        <h2 className="mb-2 text-xl font-bold text-slate-900">Notas internas</h2>
        <NoteList notes={notes} onDelete={handleDeleteNote} />
        <NoteForm onAdd={handleAddNote} loading={addingNote} />
      </section>
    </main>
  );
}