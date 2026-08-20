'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '../../lib/auth-context';

interface FieldErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
  general?: string;
}

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): boolean {
    const errors: FieldErrors = {};

    if (!email) {
      errors.email = 'El correo es obligatorio';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Formato de correo invalido';
    }

    if (!password) {
      errors.password = 'La contrasena es obligatoria';
    } else if (password.length < 6) {
      errors.password = 'Minimo 6 caracteres';
    }

    if (password !== confirmPassword) {
      errors.confirmPassword = 'Las contrasenas no coinciden';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFieldErrors({});

    if (!validate()) return;

    setSubmitting(true);

    try {
      await register({
        email,
        password,
        profile: {
          ...(name ? { name } : {}),
          ...(phone ? { phone } : {}),
        },
      });
      router.push('/');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al registrarse';

      // Try to map known backend errors to fields
      if (msg.toLowerCase().includes('email') && msg.toLowerCase().includes('exist')) {
        setFieldErrors({ email: 'Este correo ya esta registrado' });
      } else if (msg.toLowerCase().includes('password')) {
        setFieldErrors({ password: msg });
      } else {
        setFieldErrors({ general: msg });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="surface-card p-8">
          <div className="mb-6 text-center">
            <span className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-brand text-lg font-extrabold text-white">
              NX
            </span>
            <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-slate-900">
              Crear cuenta
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Registrate para acceder al backoffice
            </p>
          </div>

          {fieldErrors.general && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {fieldErrors.general}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name (optional) */}
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-semibold text-slate-700">
                Nombre <span className="font-normal text-slate-400">(opcional)</span>
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
                placeholder="Tu nombre"
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-semibold text-slate-700">
                Correo electronico *
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`w-full rounded-lg border px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-brand/20 ${
                  fieldErrors.email
                    ? 'border-red-400 focus:border-red-500'
                    : 'border-slate-300 focus:border-brand'
                }`}
                placeholder="tu@email.com"
              />
              {fieldErrors.email && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.email}</p>
              )}
            </div>

            {/* Phone (optional) */}
            <div>
              <label htmlFor="phone" className="mb-1 block text-sm font-semibold text-slate-700">
                Telefono <span className="font-normal text-slate-400">(opcional)</span>
              </label>
              <input
                id="phone"
                type="tel"
                autoComplete="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/20"
                placeholder="+34 600 000 000"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-semibold text-slate-700">
                Contrasena *
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`w-full rounded-lg border px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-brand/20 ${
                  fieldErrors.password
                    ? 'border-red-400 focus:border-red-500'
                    : 'border-slate-300 focus:border-brand'
                }`}
                placeholder="Minimo 6 caracteres"
              />
              {fieldErrors.password && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.password}</p>
              )}
            </div>

            {/* Confirm password */}
            <div>
              <label htmlFor="confirmPassword" className="mb-1 block text-sm font-semibold text-slate-700">
                Confirmar contrasena *
              </label>
              <input
                id="confirmPassword"
                type="password"
                required
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`w-full rounded-lg border px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:ring-2 focus:ring-brand/20 ${
                  fieldErrors.confirmPassword
                    ? 'border-red-400 focus:border-red-500'
                    : 'border-slate-300 focus:border-brand'
                }`}
                placeholder="Repite tu contrasena"
              />
              {fieldErrors.confirmPassword && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.confirmPassword}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-full bg-brand px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-dark disabled:opacity-50"
            >
              {submitting ? 'Creando cuenta...' : 'Crear cuenta'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Ya tienes cuenta?{' '}
            <Link href="/login" className="font-semibold text-brand hover:underline">
              Inicia sesion
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
