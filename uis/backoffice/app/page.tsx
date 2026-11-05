import Link from 'next/link';
import { toolGroups } from '@/lib/backoffice-tools';

export default function BackofficeHomePage() {
  const toolCount = toolGroups.reduce((total, group) => total + group.tools.length, 0);

  return (
    <main id="main-content" className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
      <section className="relative overflow-hidden rounded-3xl bg-slate-900 px-6 py-10 text-white sm:px-10 sm:py-14">
        <div aria-hidden="true" className="pointer-events-none absolute -right-20 -top-32 h-96 w-96 rounded-full bg-teal-700/30 blur-3xl" />
        <div className="relative">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300">Nexova / Espacio de trabajo</p>
          <h1 className="mt-5 max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
            Todo tu equipo.<br />
            Un mismo lugar.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-300">
            Menos ruido, más foco. Encuentra las herramientas que necesitas para avanzar en tu día a día.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3 text-xs font-medium text-slate-300">
            <span className="rounded-full border border-white/15 px-3 py-1.5">{toolCount} herramientas</span>
            <span className="rounded-full border border-white/15 px-3 py-1.5">{toolGroups.length} áreas de trabajo</span>
          </div>
        </div>
      </section>

      <nav aria-label="Áreas de trabajo" className="my-8 flex flex-wrap gap-2">
        {toolGroups.map((group) => (
          <a key={group.id} href={`#${group.id}`} className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-brand hover:text-brand focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">
            {group.name}
          </a>
        ))}
      </nav>

      <div className="space-y-10">
        {toolGroups.map((group) => (
          <section key={group.id} id={group.id} aria-labelledby={`${group.id}-title`} className="scroll-mt-24">
            <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <h2 id={`${group.id}-title`} className="text-xl font-semibold tracking-tight text-slate-900">{group.name}</h2>
              <p className="text-sm text-slate-500">{group.description}</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {group.tools.map((tool) => (
                <Link
                  key={tool.href}
                  href={tool.href}
                  className="group flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-6 transition hover:border-teal-300 hover:shadow-lg hover:shadow-teal-900/5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand"
                >
                  <div className="mb-5 flex items-center justify-between">
                    <span aria-hidden="true" className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-50 text-sm font-bold tracking-wide text-brand">{tool.initials}</span>
                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5 text-slate-400 transition group-hover:text-brand">
                      <path d="M7 17 17 7M7 7h10v10" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 group-hover:text-brand">{tool.name}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-500">{tool.description}</p>
                  <span className="mt-auto pt-6 text-sm font-semibold text-brand">Abrir herramienta <span aria-hidden="true">→</span></span>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}