'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useAuth } from '../../../lib/auth-context';
import { getMyProfileApi, updateMyProfileApi } from '../../../services/auth-api';

export default function AccountProfilePage() {
  const { user, logout } = useAuth();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch profile data from GET /profiles/me on mount
  useEffect(() => {
    let cancelled = false;

    async function fetchProfile() {
      try {
        const profile = await getMyProfileApi();
        if (!cancelled) {
          setName(profile.name ?? '');
          setPhone(profile.phone ?? '');
          setAddress(profile.address ?? '');
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : 'Error al cargar el perfil';
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchProfile();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSuccess(false);
    setError(null);

    try {
      await updateMyProfileApi({
        name: name || undefined,
        phone: phone || undefined,
        address: address || undefined,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al guardar';
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="surface-card p-8">
          <div className="flex items-center justify-center py-12">
            <span className="text-sm text-slate-400">Cargando perfil...</span>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="surface-card p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Mi cuenta</h1>
          <p className="mt-1 text-sm text-slate-500">
            Gestiona tu perfil y preferencias de cuenta
          </p>
        </div>

        {/* Email (read-only, from JWT) */}
        <div className="mb-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Correo electronico
          </p>
          <p className="mt-1 text-sm font-medium text-slate-900">{user?.email}</p>
        </div>

        {success && (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
            Perfil actualizado correctamente.
          </div>
        )}

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div>
            <label htmlFor="name" className="mb-1 block text-sm font-semibold text-slate-700">
              Nombre
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
              placeholder="Tu nombre"
            />
          </div>

          {/* Phone */}
          <div>
            <label htmlFor="phone" className="mb-1 block text-sm font-semibold text-slate-700">
              Telefono
            </label>
            <input
              id="phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
              placeholder="+34 600 000 000"
            />
          </div>

          {/* Address */}
          <div>
            <label htmlFor="address" className="mb-1 block text-sm font-semibold text-slate-700">
              Direccion
            </label>
            <input
              id="address"
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
              placeholder="Tu direccion"
            />
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-full bg-brand px-6 py-2.5 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-50"
            >
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </button>
            <button
              type="button"
              onClick={logout}
              className="rounded-full border border-red-300 px-6 py-2.5 text-sm font-bold text-red-600 transition hover:bg-red-50"
            >
              Cerrar sesion
            </button>
          </div>
        </form>

        {/* Link to change password */}
        <div className="mt-8 border-t border-slate-200 pt-6">
          <Link
            href="/account/change-password"
            className="inline-flex items-center gap-2 rounded-full border border-brand/30 px-5 py-2.5 text-sm font-semibold text-brand transition hover:bg-brand/5"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.529-6.53c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
            </svg>
            Cambiar contrasena
          </Link>
        </div>
      </div>
    </main>
  );
}
