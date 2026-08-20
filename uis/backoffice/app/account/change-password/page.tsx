'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { changePasswordApi } from '../../../services/auth-api';

export default function ChangePasswordPage() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError('Las contrasenas nuevas no coinciden.');
      return;
    }

    if (newPassword.length < 6) {
      setError('La contrasena debe tener al menos 6 caracteres.');
      return;
    }

    if (currentPassword === newPassword) {
      setError('La nueva contrasena debe ser diferente a la actual.');
      return;
    }

    setSubmitting(true);

    try {
      await changePasswordApi(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cambiar la contrasena';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="surface-card p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Cambiar contrasena
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Actualiza tu contrasena de acceso
          </p>
        </div>

        {success && (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
            Contrasena actualizada correctamente.
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="current-password" className="mb-1 block text-sm font-semibold text-slate-700">
              Contrasena actual
            </label>
            <input
              id="current-password"
              type="password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
              placeholder="Tu contrasena actual"
              disabled={submitting}
            />
          </div>

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
              Confirmar nueva contrasena
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
              placeholder="Repite la nueva contrasena"
              disabled={submitting}
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !currentPassword || !newPassword || !confirmPassword}
            className="w-full rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-50"
          >
            {submitting ? 'Guardando...' : 'Cambiar contrasena'}
          </button>
        </form>
      </div>
    </main>
  );
}