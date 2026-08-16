'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { forgotPasswordApi } from '../../services/auth-api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await forgotPasswordApi(email);
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al enviar la solicitud';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="surface-card p-8 text-center">
            <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-green-100">
              <svg className="h-7 w-7 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
              </svg>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
              Correo enviado
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Si esa direccion de correo esta registrada, recibiras un enlace para restablecer tu contrasena en breve.
            </p>
            <Link
              href="/login"
              className="mt-6 inline-block rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark"
            >
              Volver a iniciar sesion
            </Link>
          </div>
        </div>
      </main>
    );
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
              Olvidaste tu contrasena?
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Introduce tu correo y te enviaremos un enlace para restablecerla
            </p>
          </div>

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
                disabled={submitting}
              />
            </div>

            <button
              type="submit"
              disabled={submitting || !email}
              className="w-full rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-50"
            >
              {submitting ? 'Enviando...' : 'Enviar enlace'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            <Link href="/login" className="font-semibold text-brand hover:underline">
              Volver a iniciar sesion
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}