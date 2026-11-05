'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../lib/auth-context';
import { toolGroups } from '../lib/backoffice-tools';
import ThemeToggle from './ThemeToggle';

export default function NavBar() {
  const { user, isAuthenticated, loading, logout } = useAuth();
  const pathname = usePathname();
  const [toolsOpen, setToolsOpen] = useState(false);
  const toolsRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!toolsOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (event.target instanceof Node && !toolsRef.current?.contains(event.target)) {
        setToolsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setToolsOpen(false);
        triggerRef.current?.focus();
      }
    }

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [toolsOpen]);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/95 backdrop-blur-md">
      <div className="mx-auto flex min-h-18 w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" aria-label="Nexova Backoffice, inicio" onClick={() => setToolsOpen(false)} className="flex shrink-0 items-center gap-3 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-xs font-extrabold tracking-wide text-white">NX</span>
          <span className="hidden sm:block">
            <span className="block text-base font-bold tracking-tight text-slate-900">Nexova</span>
            <span className="block text-xs text-slate-500">Backoffice</span>
          </span>
        </Link>

        <nav className="flex min-w-0 flex-wrap items-center justify-end gap-1 sm:gap-4" aria-label="Navegación principal">
          <div
            ref={toolsRef}
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget)) setToolsOpen(false);
            }}
          >
            <button
              ref={triggerRef}
              type="button"
              aria-expanded={toolsOpen}
              aria-controls="backoffice-tools"
              onClick={() => setToolsOpen(!toolsOpen)}
              className="inline-flex items-center gap-1 rounded-xl bg-slate-100 px-2 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand sm:gap-2 sm:px-3 sm:text-sm"
            >
              Herramientas
              <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={`h-4 w-4 transition-transform ${toolsOpen ? 'rotate-180' : ''}`}>
                <path d="m5 7.5 5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {toolsOpen && (
              <div id="backoffice-tools" className="absolute inset-x-4 top-full mt-2 max-h-[calc(100dvh-6rem)] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 shadow-xl shadow-slate-900/10 sm:inset-x-auto sm:right-6 sm:w-[min(36rem,calc(100vw-3rem))] sm:p-6">
                <Link href="/" onClick={() => setToolsOpen(false)} aria-current={pathname === '/' ? 'page' : undefined} className="mb-5 flex items-center justify-between rounded-lg bg-teal-50 px-3 py-3 text-sm font-semibold text-brand focus-visible:outline-2 focus-visible:outline-brand">
                  Ver todas las herramientas <span aria-hidden="true">→</span>
                </Link>
                <div className="grid gap-5 sm:grid-cols-2">
                  {toolGroups.map((group) => (
                    <div key={group.id}>
                      <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{group.name}</p>
                      <ul className="space-y-1">
                        {group.tools.map((tool) => {
                          const active = pathname === tool.href || (tool.href === '/inventory/products' ? pathname.startsWith('/inventory/') : pathname.startsWith(`${tool.href}/`));
                          return (
                            <li key={tool.href}>
                              <Link
                                href={tool.href}
                                aria-current={active ? 'page' : undefined}
                                onClick={() => setToolsOpen(false)}
                                className={`block rounded-lg px-3 py-2 text-sm transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-brand ${active ? 'bg-teal-50 font-semibold text-brand' : 'text-slate-700'}`}
                              >
                                {tool.name}
                              </Link>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <ThemeToggle />

          {loading ? (
            <span role="status" className="text-sm text-slate-400">Cargando...</span>
          ) : isAuthenticated ? (
            <div className="flex min-w-0 items-center gap-1 border-l border-slate-200 pl-2 sm:gap-2 sm:pl-4">
              <Link
                href="/account/profile"
                aria-label={`Mi perfil: ${user?.profile?.name || user?.email || 'Usuario'}`}
                title={user?.profile?.name || user?.email}
                onClick={() => setToolsOpen(false)}
                className="flex min-w-0 items-center gap-2 rounded-xl p-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-brand"
              >
                <span aria-hidden="true" className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-50 text-xs font-bold text-brand">{user?.email?.charAt(0).toUpperCase() ?? 'U'}</span>
                <span className="hidden max-w-32 truncate lg:block">{user?.profile?.name || user?.email}</span>
              </Link>
              <button
                type="button"
                onClick={() => { setToolsOpen(false); logout(); }}
                aria-label="Cerrar sesión"
                title="Cerrar sesión"
                className="inline-flex items-center gap-2 rounded-xl p-2.5 text-sm font-medium text-slate-500 transition hover:bg-red-50 hover:text-red-600 focus-visible:outline-2 focus-visible:outline-brand"
              >
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-5 w-5">
                  <path d="M9 5H5v14h4m5-14 7 7-7 7m-5-7h12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span className="hidden sm:inline">Salir</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1 sm:gap-2">
              <Link href="/login" onClick={() => setToolsOpen(false)} className="rounded-xl px-2 py-2.5 text-sm font-semibold text-slate-600 hover:text-brand sm:px-3">
                Entrar
              </Link>
              <Link href="/register" aria-label="Crear cuenta" onClick={() => setToolsOpen(false)} className="rounded-xl bg-brand px-2 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-dark sm:px-4">
                <span className="sm:hidden">Registro</span>
                <span className="hidden sm:inline">Crear cuenta</span>
              </Link>
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
