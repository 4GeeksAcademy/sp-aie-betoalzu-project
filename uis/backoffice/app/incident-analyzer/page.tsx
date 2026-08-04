import IncidentAnalyzerClient from '@/components/IncidentAnalyzerClient';

export default function IncidentAnalyzerPage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-8 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
          Calidad de datos
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">Analizador de Incidentes</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Sube un archivo CSV de soporte para validar datos, revisar el resumen operativo y exportar metricas.
        </p>
      </section>

      <IncidentAnalyzerClient />
    </main>
  );
}