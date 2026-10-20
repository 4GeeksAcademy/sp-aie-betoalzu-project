'use client';

import { useEffect, useState } from 'react';
import { getAuthHeaders } from '../../lib/auth-token';

type QueryResponse = { answer: string };

export default function KnowledgePage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [source, setSource] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleQuery = async () => {
    const trimmed = question.trim();
    if (!trimmed || trimmed.length > 2000) return;

    setLoading(true);
    setError('');
    setAnswer('');
    setSource('');

    try {
      const response = await fetch('/api/knowledge/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ question: trimmed }),
      });

      if (response.status === 401 || response.status === 403) {
        setError('Sesión expirada. Inicia sesión nuevamente.');
        return;
      }

      if (response.status === 422) {
        setError('La pregunta debe tener entre 1 y 2000 caracteres.');
        return;
      }

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(body.detail || body.error || 'Error al consultar la base de conocimiento.');
        return;
      }

      const data = (await response.json()) as QueryResponse;
      setAnswer(data.answer);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión con el servidor.');
    } finally {
      setLoading(false);
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
            {loading ? 'Consultando...' : 'Consultar'}
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