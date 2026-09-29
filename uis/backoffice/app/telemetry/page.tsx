'use client';

import { useEffect, useState } from 'react';

type ReportMetricItem = {
  date?: string;
  event_type?: string;
  count?: number;
  error_count?: number;
  avg_latency_ms?: number;
  failure_rate?: number;
};

type TelemetryReport = {
  period: { from: string; to: string };
  metrics: {
    events_per_day: ReportMetricItem[];
    error_rate_by_type: ReportMetricItem[];
    latency_by_day: ReportMetricItem[];
    auth_failure_rate: ReportMetricItem[];
  };
};

const formatPercent = (value: number | undefined) => {
  if (value === undefined || Number.isNaN(value)) return 'N/A';
  return `${(value * 100).toFixed(1)}%`;
};

const formatNumber = (value: number | undefined) => {
  if (value === undefined || Number.isNaN(value)) return 'N/A';
  return value.toLocaleString();
};

export default function TelemetryDashboardPage() {
  const [report, setReport] = useState<TelemetryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadReport = async () => {
      try {
        const response = await fetch('http://localhost:8000/telemetry/report');
        if (!response.ok) {
          throw new Error('No se pudo obtener el reporte de telemetría');
        }
        const payload = (await response.json()) as TelemetryReport;
        setReport(payload);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al cargar el reporte');
      } finally {
        setLoading(false);
      }
    };

    loadReport();
  }, []);

  if (loading) {
    return <main className="mx-auto max-w-6xl px-4 py-10 text-slate-700">Cargando reporte técnico…</main>;
  }

  if (error || !report) {
    return <main className="mx-auto max-w-6xl px-4 py-10 text-red-700">{error || 'Sin datos disponibles'}</main>;
  }

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-10">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700">Telemetría técnica</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Reporte operativo</h1>
        <p className="mt-2 text-sm text-slate-600">
          Periodo: {report.period.from} → {report.period.to}
        </p>
      </header>

      <section className="grid gap-6 lg:grid-cols-2">
        <MetricCard title="Volumen de eventos por día" rows={report.metrics.events_per_day} columns={['date', 'count']} formatter={(row) => ({
          label: row.date || 'N/A',
          value: formatNumber(row.count),
        })} />

        <MetricCard title="Tasa de error por tipo" rows={report.metrics.error_rate_by_type} columns={['event_type', 'error_count']} formatter={(row) => ({
          label: row.event_type || 'N/A',
          value: formatNumber(row.error_count),
        })} />

        <MetricCard title="Latencia media por día" rows={report.metrics.latency_by_day} columns={['date', 'avg_latency_ms']} formatter={(row) => ({
          label: row.date || 'N/A',
          value: `${formatNumber(row.avg_latency_ms)} ms`,
        })} />

        <MetricCard title="Fallo de autenticación" rows={report.metrics.auth_failure_rate} columns={['date', 'failure_rate']} formatter={(row) => ({
          label: row.date || 'N/A',
          value: formatPercent(row.failure_rate),
        })} />
      </section>
    </main>
  );
}

type MetricCardProps = {
  title: string;
  rows: ReportMetricItem[];
  columns: string[];
  formatter: (row: ReportMetricItem) => { label: string; value: string };
};

function MetricCard({ title, rows, formatter }: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">{title}</h2>
      <div className="space-y-3">
        {rows.length === 0 ? (
          <p className="text-sm text-slate-500">Sin datos en este periodo.</p>
        ) : (
          rows.map((row, index) => {
            const item = formatter(row);
            return (
              <div key={`${title}-${index}`} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium text-slate-700">{item.label}</span>
                <span className="text-slate-900">{item.value}</span>
              </div>
            );
          })
        )}
      </div>
    </article>
  );
}
