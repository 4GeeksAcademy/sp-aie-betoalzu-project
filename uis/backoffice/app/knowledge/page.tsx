'use client';

import { useEffect, useRef, useState } from 'react';
import { getAuthHeaders } from '../../lib/auth-token';

type JobResponse =
  | { job_id: string; status: 'pending' }
  | { job_id: string; status: 'completed'; answer: string }
  | { job_id: string; status: 'failed'; detail: string };

async function requestJob(url: string, init: RequestInit): Promise<JobResponse> {
  const response = await fetch(url, init);
  if (response.status === 401 || response.status === 403) {
    throw new Error('Sesión expirada. Inicia sesión nuevamente.');
  }
  const body: unknown = await response.json();
  if (!response.ok) {
    const message = body && typeof body === 'object'
      ? ('detail' in body ? body.detail : 'error' in body ? body.error : undefined)
      : undefined;
    throw new Error(typeof message === 'string'
      ? message : 'Error al consultar la base de conocimiento.');
  }
  if (!body || typeof body !== 'object'
    || !('job_id' in body) || typeof body.job_id !== 'string'
    || !('status' in body)
    || !['pending', 'completed', 'failed'].includes(String(body.status))) {
    throw new Error('El servidor devolvió un estado de consulta inválido.');
  }
  if (body.status === 'completed' && 'answer' in body && typeof body.answer === 'string') {
    return { job_id: body.job_id, status: 'completed', answer: body.answer };
  }
  if (body.status === 'failed' && 'detail' in body && typeof body.detail === 'string') {
    return { job_id: body.job_id, status: 'failed', detail: body.detail };
  }
  if (body.status !== 'pending') {
    throw new Error('El servidor devolvió una consulta sin resultado.');
  }
  return { job_id: body.job_id, status: 'pending' };
}

export default function KnowledgePage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => () => activeRequest.current?.abort(), []);

  const handleQuery = async () => {
    const trimmed = question.trim();
    if (!trimmed || trimmed.length > 2000 || activeRequest.current) return;

    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError('');
    setAnswer('');

    try {
      let job = await requestJob('/api/knowledge/jobs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ question: trimmed }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
      });
      const deadline = Date.now() + 30 * 60 * 1000;
      while (job.status === 'pending') {
        await new Promise<void>((resolve) => setTimeout(resolve, 2000));
        if (controller.signal.aborted) return;
        if (Date.now() >= deadline) {
          throw new Error('La consulta está tardando demasiado. Inténtalo de nuevo más tarde.');
        }
        job = await requestJob(`/api/knowledge/jobs/${encodeURIComponent(job.job_id)}`, {
          headers: getAuthHeaders(),
          cache: 'no-store',
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
        });
      }
      if (job.status === 'failed') {
        throw new Error(job.detail);
      }
      setAnswer(job.answer);
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof Error ? err.message : 'Error de conexión con el servidor.');
      }
    } finally {
      activeRequest.current = null;
      if (!controller.signal.aborted) setLoading(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleQuery();
    }
  };

  return (
    <main className="mx-auto max-w-4xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
      <header className="border-b border-slate-200 pb-6">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand">Asistente Comercial</p>
        <h1 className="mt-2 text-3xl font-extrabold text-slate-900">Base de conocimiento Nexova</h1>
        <p className="mt-2 text-sm text-slate-600">
          Consulta información sobre servicios, pricing, SLA y procesos comerciales de Nexova.
          El asistente responderá basándose exclusivamente en la documentación indexada.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="px-5 py-4">
          <label htmlFor="question-input" className="mb-1 block text-sm font-semibold text-slate-700">
            Tu pregunta
          </label>
          <textarea
            id="question-input"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={3}
            maxLength={2000}
            placeholder="Ej: ¿Cuál es la tarifa de Nexova?"
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
          />
          <p className="mt-1 text-xs text-slate-400">{question.length}/2000 caracteres</p>
          <button
            onClick={() => void handleQuery()}
            disabled={loading || !question.trim()}
            className="mt-3 rounded-full bg-brand px-5 py-2 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Consultando en segundo plano...' : 'Consultar'}
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {answer && (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-lg font-bold text-slate-900">Respuesta</h2>
          </div>
          <div className="px-5 py-5 text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">
            {answer}
          </div>
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-xs text-slate-500">
        <p className="font-semibold text-slate-600">ℹ️ Acerca de este asistente</p>
        <ul className="mt-2 list-disc space-y-1 pl-4">
          <li>Responde exclusivamente con información de los documentos indexados de Nexova.</li>
          <li>Las fuentes consultadas se citan al final de cada respuesta.</li>
          <li>Los tiempos de entrega son promedios, no garantías (excepto la garantía de reemplazo de 6 meses).</li>
          <li>Para descuentos sobre la tarifa del 22%, contacta a Marcos Ibáñez.</li>
        </ul>
      </section>
    </main>
  );
}