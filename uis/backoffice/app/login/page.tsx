'use client';

import { useState, type FormEvent, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '../../lib/auth-context';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const resetSuccess = searchParams.get('reset') === 'success';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password);
      router.push('/');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al iniciar sesion';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="surface-card p-8">
          <div className="mb-6 text-center">
            <span className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-brand text-lg font-extrabold text-white">
              NX
            </span>
            <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-slate-900">
              Iniciar sesion
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Accede al backoffice de Nexova
            </p>
          </div>

          {resetSuccess && (
            <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
              Contrasena restablecida correctamente. Inicia sesion con tu nueva contrasena.
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-semibold text-slate-700">
                Correo electronico
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
                placeholder="tu@email.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-semibold text-slate-700">
                Contrasena
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
                placeholder="Minimo 6 caracteres"
              />
              <div className="mt-1 text-right">
                <Link href="/forgot-password" className="text-xs font-semibold text-brand hover:underline">
                  Olvidaste tu contrasena?
                </Link>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-50"
            >
              {submitting ? 'Entrando...' : 'Entrar'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            No tienes cuenta?{' '}
            <Link href="/register" className="font-semibold text-brand hover:underline">
              Registrate
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
