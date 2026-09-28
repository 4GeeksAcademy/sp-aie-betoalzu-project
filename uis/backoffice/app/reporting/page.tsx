'use client';

import { useEffect, useState } from 'react';
import { getAuthHeaders } from '../../lib/auth-token';

type PerformanceEntry = {
  office: string;
  programme_id: string;
  total_material_cost: number;
  kits_delivered_count: number;
  shortage_events_count: number;
  cost_variance_events_count: number;
  currency: string;
};

type PerformanceReport = { week_start: string; entries: PerformanceEntry[] };

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ReportingPage() {
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [weekStart, setWeekStart] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadReport = async () => {
      setLoading(true);
      setError('');
      try {
        const query = weekStart ? `?week_start=${weekStart}` : '';
        const response = await fetch(`${apiUrl}/reporting/weekly-office-program-performance${query}`, {
          headers: getAuthHeaders(),
        });
        if (!response.ok) throw new Error('No se pudo cargar el reporte semanal');
        setReport((await response.json()) as PerformanceReport);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al cargar el reporte');
      } finally {
        setLoading(false);
      }
    };

    void loadReport();
  }, [weekStart]);

  const entries = report?.entries ?? [];
  const totalCost = entries.reduce((sum, entry) => sum + entry.total_material_cost, 0);
  const kitsDelivered = entries.reduce((sum, entry) => sum + entry.kits_delivered_count, 0);
  const shortages = entries.reduce((sum, entry) => sum + entry.shortage_events_count, 0);
  const costVariances = entries.reduce((sum, entry) => sum + entry.cost_variance_events_count, 0);

  return (
    <main className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-5 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-brand">Desempeño de negocio</p>
          <h1 className="mt-2 text-3xl font-extrabold text-slate-900">Reporte semanal por oficina y programa</h1>
          <p className="mt-2 text-sm text-slate-600">Inversión y entrega de material de formación para L&amp;D.</p>
        </div>
        <label className="text-sm font-semibold text-slate-700">
          Semana que consultar
          <input
            type="date"
            value={weekStart}
            onChange={(event) => setWeekStart(event.target.value)}
            className="mt-2 block rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal"
          />
        </label>
      </header>

      {loading && <p className="text-slate-600">Cargando reporte semanal...</p>}
      {error && <p className="rounded-lg bg-red-50 p-4 text-red-700">{error}</p>}
      {!loading && !error && report && (
        <>
          <p className="text-sm font-semibold text-slate-600">Periodo: semana del {report.week_start}</p>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Indicadores semanales">
            <KpiCard label="Costo de material por oficina/programa" value={totalCost.toLocaleString('es-ES', { minimumFractionDigits: 2 })} detail="Moneda local" />
            <KpiCard label="Kits entregados" value={kitsDelivered.toLocaleString('es-ES')} detail="Unidades" />
            <KpiCard label="Frecuencia de escasez" value={shortages.toLocaleString('es-ES')} detail="Eventos" />
            <KpiCard label="Frecuencia de variación de costo" value={costVariances.toLocaleString('es-ES')} detail="Eventos" />
          </section>

          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 py-4">
              <h2 className="text-lg font-bold text-slate-900">Detalle por oficina y programa</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>{['Oficina', 'Programa', 'Costo', 'Kits entregados', 'Escasez', 'Variación de costo'].map((heading) => <th key={heading} className="px-5 py-3 font-bold">{heading}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {entries.length === 0 ? <tr><td colSpan={6} className="px-5 py-8 text-center text-slate-500">No hay datos para esta semana.</td></tr> : entries.map((entry) => (
                    <tr key={`${entry.office}-${entry.programme_id}`} className="text-slate-700">
                      <td className="px-5 py-4 font-semibold capitalize">{entry.office}</td>
                      <td className="px-5 py-4">{entry.programme_id}</td>
                      <td className="px-5 py-4">{entry.total_material_cost.toLocaleString('es-ES', { style: 'currency', currency: entry.currency })}</td>
                      <td className="px-5 py-4">{entry.kits_delivered_count}</td>
                      <td className="px-5 py-4">{entry.shortage_events_count}</td>
                      <td className="px-5 py-4">{entry.cost_variance_events_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function KpiCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm font-semibold text-slate-600">{label}</p><p className="mt-4 text-3xl font-extrabold text-brand">{value}</p><p className="mt-1 text-xs uppercase tracking-wide text-slate-400">{detail}</p></article>;
}
