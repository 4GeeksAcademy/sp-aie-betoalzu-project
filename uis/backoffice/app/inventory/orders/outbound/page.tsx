'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { createOutboundOrder, fetchProduct } from '@/lib/inventory';
import { getStoredToken } from '@/lib/auth-token';
import { OFFICES, EXIT_TYPES, EXIT_TYPE_LABELS, type Office, type ExitType } from '@/types/inventory';

const initialForm = {
  asset_id: 0,
  asset_name: '',
  quantity: 1,
  exit_type: 'allocation' as ExitType,
  assigned_to: '',
  office: 'Valencia' as Office,
};

export default function OutboundOrderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [form, setForm] = useState(initialForm);
  const [currentStock, setCurrentStock] = useState<number | null>(null);
  const [stockLoading, setStockLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.push('/login?from=/inventory/orders/outbound');
      return;
    }

    const assetId = searchParams.get('asset_id');
    const name = searchParams.get('name');
    if (assetId) {
      setForm((prev) => ({ ...prev, asset_id: Number(assetId), asset_name: name || '' }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch current stock when asset_id changes
  const fetchStock = useCallback(async (assetId: number) => {
    if (assetId <= 0) {
      setCurrentStock(null);
      return;
    }
    setStockLoading(true);
    try {
      const product = await fetchProduct(assetId);
      setCurrentStock(product.current_stock);
    } catch {
      setCurrentStock(null);
    } finally {
      setStockLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStock(form.asset_id);
  }, [form.asset_id, fetchStock]);

  const hasInsufficientStock =
    currentStock !== null && form.quantity > currentStock;

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]:
        name === 'asset_id' || name === 'quantity'
          ? Number(value)
          : value,
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
      await createOutboundOrder({
        asset_id: form.asset_id,
        quantity: form.quantity,
        exit_type: form.exit_type,
        assigned_to: form.exit_type === 'allocation' ? form.assigned_to : null,
        office: form.office,
      });
      setSuccess('Salida registrada con éxito.');
      setForm(initialForm);
      setCurrentStock(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrar la salida.');
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
          Formulario de Salida
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Registra una asignación o consumo de activos del inventario.
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

          {/* Asset ID / Product name */}
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
                {stockLoading && (
                  <span className="ml-auto text-xs text-slate-400">Consultando stock...</span>
                )}
                {currentStock !== null && !stockLoading && (
                  <span className="ml-auto text-xs text-slate-500">
                    Stock actual: <span className="font-semibold">{currentStock} uds.</span>
                  </span>
                )}
              </div>
            ) : (
              <div>
                <input
                  id="asset_id"
                  name="asset_id"
                  type="number"
                  min={1}
                  required
                  value={form.asset_id || ''}
                  onChange={handleChange}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
                  placeholder="ID del Producto (Ej: 1)"
                />
                {stockLoading && (
                  <p className="mt-1 text-xs text-slate-400">Consultando stock...</p>
                )}
                {currentStock !== null && !stockLoading && (
                  <p className="mt-1 text-xs text-slate-500">
                    Stock actual: <span className="font-semibold">{currentStock} uds.</span>
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Quantity */}
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
              className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 ${
                hasInsufficientStock
                  ? 'border-red-400 bg-red-50 focus:border-red-500 focus:ring-red-200'
                  : 'border-slate-300 focus:border-brand focus:ring-brand/20'
              }`}
              placeholder="Ej: 3"
            />
            {hasInsufficientStock && (
              <p className="mt-1 text-xs text-red-600">
                La cantidad solicitada ({form.quantity} uds.) supera el stock disponible ({currentStock} uds.). Reduce la cantidad o registra una entrada primero.
              </p>
            )}
          </div>

          {/* Exit type */}
          <div className="mb-4">
            <label htmlFor="exit_type" className="mb-1 block text-sm font-medium text-slate-700">
              Tipo de salida
            </label>
            <select
              id="exit_type"
              name="exit_type"
              required
              value={form.exit_type}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
            >
              {EXIT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {EXIT_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>

          {/* Assigned to (only for allocation) */}
          {form.exit_type === 'allocation' && (
            <div className="mb-4">
              <label htmlFor="assigned_to" className="mb-1 block text-sm font-medium text-slate-700">
                Asignado a
              </label>
              <input
                id="assigned_to"
                name="assigned_to"
                type="text"
                required
                value={form.assigned_to}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
                placeholder="Nombre o ID del empleado"
              />
            </div>
          )}

          {/* Office */}
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

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting || hasInsufficientStock}
            className="inline-flex w-full items-center justify-center rounded-lg bg-brand px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand/90 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Registrando...' : 'Registrar salida'}
          </button>
        </form>
      </div>
    </main>
  );
}