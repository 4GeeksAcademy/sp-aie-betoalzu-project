import RfpIntakeClient from '@/components/RfpIntakeClient';

export default function RfpIntakePage() {
  return (
    <main className="mx-auto w-full max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
      <header className="rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
          Operaciones comerciales
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Recepción y análisis de RFPs
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Recibe solicitudes PDF, consulta el estado de cada ticket y comparte con Ventas los datos,
          preguntas abiertas y aspectos de los departamentos activos.
        </p>
      </header>
      <RfpIntakeClient />
    </main>
  );
}
