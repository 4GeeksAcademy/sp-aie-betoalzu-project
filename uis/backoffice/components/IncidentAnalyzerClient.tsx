'use client';

import { FormEvent, useMemo, useState } from 'react';
import { analyzeIncidentsCsv, exportIncidentResults, CsvIncidentSummary } from '@/services/api';

const INVALID_RULE_LABELS: Record<string, string> = {
  missing_client_company: 'Falta client_company',
  invalid_category: 'Categoria invalida o ausente',
  invalid_description: 'Descripcion ausente o demasiado corta',
  invalid_agent: 'agent_id invalido o ausente',
  invalid_status: 'status invalido o ausente',
  invalid_email: 'Email invalido o ausente',
  closed_no_score: 'Ticket CLOSED sin puntuacion',
  score_out_of_range: 'Puntuacion fuera de rango (1-5)',
};

function percentage(part: number, total: number) {
  if (!total) return '0.0%';
  return `${((part / total) * 100).toFixed(1)}%`;
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export default function IncidentAnalyzerClient() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<CsvIncidentSummary | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState('');

  const activeInvalidRules = useMemo(() => {
    if (!summary) return [];
    return Object.entries(summary.invalid_rules).filter(([, count]) => count > 0);
  }, [summary]);

  async function onAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');

    if (!selectedFile) {
      setError('Selecciona un archivo CSV para analizar.');
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
      setError('El archivo debe tener extension .csv');
      return;
    }

    setIsAnalyzing(true);
    try {
      const result = await analyzeIncidentsCsv(selectedFile);
      setSummary(result);
    } catch (err) {
      setSummary(null);
      setError(err instanceof Error ? err.message : 'No se pudo analizar el archivo.');
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function onDownload() {
    setError('');
    setIsDownloading(true);

    try {
      const { blob, fileName } = await exportIncidentResults();
      downloadBlob(blob, fileName);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo descargar el resumen.');
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="surface-card p-6 sm:p-8">
        <h2 className="text-xl font-bold text-slate-900">Subir archivo de incidentes</h2>
        <p className="mt-1 text-sm text-slate-600">
          Carga un CSV para analizar validez de datos, distribucion por categoria/estado y nivel de satisfaccion.
        </p>

        <form onSubmit={onAnalyze} className="mt-5 space-y-4">
          <div>
            <label htmlFor="incident-csv" className="mb-2 block text-sm font-semibold text-slate-700">
              Archivo CSV
            </label>
            <input
              id="incident-csv"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                const file = event.target.files?.[0] || null;
                setSelectedFile(file);
              }}
              className="block w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 file:mr-4 file:rounded-full file:border-0 file:bg-brand file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-brand-dark"
            />
          </div>

          <button
            type="submit"
            disabled={isAnalyzing}
            className="inline-flex items-center justify-center rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isAnalyzing ? 'Analizando...' : 'Analizar archivo'}
          </button>
        </form>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900">
            <p className="font-semibold">Error</p>
            <p>{error}</p>
          </div>
        )}
      </section>

      {summary && (
        <section className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <article className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Registros totales</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{summary.total_records}</p>
            </article>
            <article className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Validos</p>
              <p className="mt-2 text-3xl font-black text-emerald-700">{summary.valid_records}</p>
            </article>
            <article className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Invalidos</p>
              <p className="mt-2 text-3xl font-black text-amber-700">{summary.invalid_records}</p>
            </article>
            <article className="surface-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Promedio satisfaccion</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{summary.average_score.toFixed(2)}/5</p>
            </article>
          </div>

          <div className="surface-card p-6">
            <h3 className="text-lg font-bold text-slate-900">Alertas de datos invalidos</h3>
            <p className="mt-1 text-sm text-slate-600">
              {summary.invalid_records} registros invalidos detectados en {summary.source_file}.
            </p>

            {activeInvalidRules.length === 0 ? (
              <p className="mt-4 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-900">
                No se detectaron incidencias de calidad de datos.
              </p>
            ) : (
              <ul className="mt-4 grid gap-3 sm:grid-cols-2">
                {activeInvalidRules.map(([rule, count]) => (
                  <li key={rule} className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <p className="font-semibold">{INVALID_RULE_LABELS[rule] || rule}</p>
                    <p className="mt-1">{count} caso(s)</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <article className="surface-card p-6">
              <h3 className="text-lg font-bold text-slate-900">Categorias (validos)</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {Object.entries(summary.categories).map(([category, count]) => (
                  <li key={category} className="flex items-center justify-between">
                    <span>{category}</span>
                    <span className="font-semibold">{count}</span>
                  </li>
                ))}
              </ul>
            </article>

            <article className="surface-card p-6">
              <h3 className="text-lg font-bold text-slate-900">Estados (validos)</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {Object.entries(summary.statuses).map(([status, count]) => (
                  <li key={status} className="flex items-center justify-between">
                    <span>{status}</span>
                    <span className="font-semibold">
                      {count} <span className="text-slate-500">({percentage(count, summary.valid_records)})</span>
                    </span>
                  </li>
                ))}
              </ul>
            </article>

            <article className="surface-card p-6">
              <h3 className="text-lg font-bold text-slate-900">Satisfaccion (tickets CLOSED)</h3>
              <p className="mt-2 text-sm text-slate-700">
                Tickets con score: <span className="font-semibold">{summary.scored_tickets}</span> de{' '}
                <span className="font-semibold">{summary.closed_tickets}</span>
              </p>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {Object.entries(summary.scores).map(([score, count]) => (
                  <li key={score} className="flex items-center justify-between">
                    <span>Puntuacion {score}</span>
                    <span className="font-semibold">{count}</span>
                  </li>
                ))}
              </ul>
            </article>
          </div>

          <div>
            <button
              type="button"
              onClick={onDownload}
              disabled={isDownloading}
              className="inline-flex items-center justify-center rounded-full bg-slate-900 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isDownloading ? 'Descargando...' : 'Descargar resumen CSV'}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}