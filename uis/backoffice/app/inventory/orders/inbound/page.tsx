'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createInboundOrder } from '@/lib/inventory';
import { getStoredToken } from '@/lib/auth-token';
import { OFFICES, type Office } from '@/types/inventory';

const initialForm = {
  asset_id: 0,
  asset_name: '',
  quantity: 1,
  supplier: '',
  office: 'Valencia' as Office,
};

function InboundOrderForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.push('/login?from=/inventory/orders/inbound');
      return;
    }

    const assetId = searchParams.get('asset_id');
    const name = searchParams.get('name');
    if (assetId) {
      setForm((prev) => ({ ...prev, asset_id: Number(assetId), asset_name: name || '' }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: name === 'asset_id' || name === 'quantity' ? Number(value) : value,
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.asset_id || form.asset_id <= 0) {
      setError('Debes seleccionar un producto desde el listado de inventario.');
      return;
    }
    setSubmitting(true);
    setError('');
    setSuccess('');

    try {
      await createInboundOrder({
        asset_id: form.asset_id,
        quantity: form.quantity,
        supplier: form.supplier,
        office: form.office,
      });
      setSuccess('Entrada registrada con éxito.');
      setForm(initialForm);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar la entrada.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-8 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
          Inventario
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Formulario de Entrada
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Registra una compra o entrega recibida de activos o productos.
        </p>
      </section>

      <div className="mx-auto max-w-lg">
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          {success && (
            <div className="mb-4 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
              {success}
            </div>
          )}

          {error && (
            <div className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Producto
            </label>
            {form.asset_name ? (
              <div className="flex items-center gap-3 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
                <span className="font-medium">{form.asset_name}</span>
              </div>
            ) : (
              <p className="text-sm text-slate-400 italic">
                Selecciona un producto desde el listado de inventario.
              </p>
            )}
          </div>

          <div className="mb-4">
            <label htmlFor="quantity" className="mb-1 block text-sm font-medium text-slate-700">
              Cantidad
            </label>
            <input
              id="quantity"
              name="quantity"
              type="number"
              min={1}
              required
              value={form.quantity}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
              placeholder="Ej: 10"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="supplier" className="mb-1 block text-sm font-medium text-slate-700">
              Proveedor
            </label>
            <input
              id="supplier"
              name="supplier"
              type="text"
              required
              value={form.supplier}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
              placeholder="Ej: Nexova Supplies S.L."
            />
          </div>

          <div className="mb-6">
            <label htmlFor="office" className="mb-1 block text-sm font-medium text-slate-700">
              Oficina
            </label>
            <select
              id="office"
              name="office"
              required
              value={form.office}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
            >
              {OFFICES.map((office) => (
                <option key={office} value={office}>
                  {office}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex w-full items-center justify-center rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand/90 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Registrando...' : 'Registrar entrada'}
          </button>
        </form>
      </div>
    </main>
  );
}

export default function InboundOrderPage() {
  return (
    <Suspense>
      <InboundOrderForm />
    </Suspense>
  );
}