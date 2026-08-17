'use client';

import Link from 'next/link';
import { useAuth } from '../lib/auth-context';

export default function NavBar() {
  const { user, isAuthenticated, loading, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand text-sm font-extrabold text-white">
            NX
          </span>
          <span className="text-lg font-extrabold tracking-tight text-brand">Nexova Backoffice</span>
        </Link>

        <nav className="flex items-center gap-2 sm:gap-4" aria-label="Navegacion principal">
          {loading ? (
            <span className="text-sm text-slate-400">...</span>
          ) : isAuthenticated ? (
            <>
              <Link href="/" className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand">
                Herramientas
              </Link>
              <Link
                href="/talent-pipeline-tracker"
                className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand"
              >
                Talent Pipeline Tracker
              </Link>
              <Link
                href="/incident-analyzer"
                className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand"
              >
                Analizador de Incidentes
              </Link>
              <Link
                href="/incidents"
                className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand"
              >
                Incidencias
              </Link>
              <Link
                href="/talent-pipeline-tracker/Candidates/new"
                className="rounded-full bg-brand px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-dark"
              >
                Registrar nueva
              </Link>

              {/* Profile & Logout */}
              <div className="ml-2 flex items-center gap-2 border-l border-slate-200 pl-4">
                <Link
                  href="/account/profile"
                  className="flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 hover:text-brand"
                >
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand/10 text-xs font-bold text-brand">
                    {user?.email?.charAt(0).toUpperCase() ?? 'U'}
                  </span>
                  <span className="hidden sm:inline">{user?.profile?.name || user?.email}</span>
                </Link>
                <button
                  onClick={logout}
                  className="rounded-full px-3 py-2 text-sm font-semibold text-slate-500 transition hover:bg-red-50 hover:text-red-600"
                >
                  Salir
                </button>
              </div>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-full px-4 py-2 text-sm font-semibold text-slate-700 transition hover:text-brand"
              >
                Iniciar sesion
              </Link>
              <Link
                href="/register"
                className="rounded-full bg-brand px-4 py-2 text-sm font-bold text-white transition hover:bg-brand-dark"
              >
                Crear cuenta
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
