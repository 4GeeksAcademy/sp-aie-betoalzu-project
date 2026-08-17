'use client';

import { useState, type FormEvent, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { resetPasswordApi } from '../../services/auth-api';

function ResetForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!token) {
    return (
      <main className="mx-auto flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="surface-card p-8 text-center">
            <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
              <svg className="h-7 w-7 text-red-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
            </div>
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
              Enlace invalido
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              El enlace de restablecimiento no es valido o ha expirado. Solicita uno nuevo.
            </p>
            <Link
              href="/forgot-password"
              className="mt-6 inline-block rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark"
            >
              Solicitar nuevo enlace
            </Link>
          </div>
        </div>
      </main>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError('Las contrasenas no coinciden.');
      return;
    }

    if (newPassword.length < 6) {
      setError('La contrasena debe tener al menos 6 caracteres.');
      return;
    }

    setSubmitting(true);

    try {
      await resetPasswordApi(token!, newPassword);
      router.push('/login?reset=success');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al restablecer la contrasena';
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
              Nueva contrasena
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Introduce tu nueva contrasena
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="new-password" className="mb-1 block text-sm font-semibold text-slate-700">
                Nueva contrasena
              </label>
              <input
                id="new-password"
                type="password"
                required
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
                placeholder="Minimo 6 caracteres"
                disabled={submitting}
              />
            </div>

            <div>
              <label htmlFor="confirm-password" className="mb-1 block text-sm font-semibold text-slate-700">
                Confirmar contrasena
              </label>
              <input
                id="confirm-password"
                type="password"
                required
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
                placeholder="Repite la contrasena"
                disabled={submitting}
              />
            </div>

            <button
              type="submit"
              disabled={submitting || !newPassword || !confirmPassword}
              className="w-full rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-50"
            >
              {submitting ? 'Restableciendo...' : 'Restablecer contrasena'}
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

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}