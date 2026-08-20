import Link from 'next/link';

const tools = [
  {
    name: 'Talent Pipeline Tracker',
    description: 'Gestiona candidaturas, filtros, etapas y notas internas del equipo de seleccion.',
    href: '/talent-pipeline-tracker',
  },
  {
    name: 'Analizador de Incidentes',
    description: 'Carga CSV de tickets para validar datos, detectar errores y exportar resumen operativo.',
    href: '/incident-analyzer',
  },
  {
    name: 'Gestor Centralizado de Incidencias',
    description: 'Registra, clasifica y da seguimiento a incidencias tecnicas, operativas y de clientes con dashboard ejecutivo.',
    href: '/incidents',
  },
  {
    name: 'Gestion de Proveedores',
    description: 'Consulta, crea, actualiza y elimina proveedores con seguimiento de estado activo o suspendido.',
    href: '/suppliers',
  },
];

export default function BackofficeHomePage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-8 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
          Panel de administracion
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">Nexova Backoffice</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Selecciona una herramienta para operar procesos internos desde un unico punto de acceso.
        </p>
      </section>

      <section>
        <h2 className="mb-4 text-xl font-bold text-slate-900">Herramientas disponibles</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {tools.map((tool) => (
            <article key={tool.name} className="surface-card flex h-full flex-col justify-between p-6">
              <div>
                <h3 className="text-lg font-bold text-slate-900">{tool.name}</h3>
                <p className="mt-2 text-sm text-slate-600">{tool.description}</p>
              </div>
              <Link
                href={tool.href}
                className="mt-5 inline-flex w-fit items-center justify-center rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark"
              >
                Abrir herramienta
              </Link>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}