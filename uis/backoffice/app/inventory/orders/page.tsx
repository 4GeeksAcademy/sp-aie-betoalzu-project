'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchOrders } from '@/lib/inventory';
import { getStoredToken } from '@/lib/auth-token';
import type { Order } from '@/types/inventory';

type FilterType = 'all' | 'entry' | 'exit';

const TIME_RANGES = [
  { label: 'Todo', value: 0 },
  { label: 'Últimas 24h', value: 1 },
  { label: 'Últimos 7 días', value: 7 },
  { label: 'Últimos 30 días', value: 30 },
  { label: 'Últimos 90 días', value: 90 },
] as const;

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
}

export default function OrdersHistoryPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterType, setFilterType] = useState<FilterType>('all');
  const [filterDays, setFilterDays] = useState<number>(0);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.push('/login?from=/inventory/orders');
      return;
    }

    loadOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadOrders() {
    setLoading(true);
    setError('');
    try {
      const data = await fetchOrders();
      setOrders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar el historial de pedidos.');
    } finally {
      setLoading(false);
    }
  }

  const filteredOrders = useMemo(() => {
    let result = [...orders];

    // Filter by type
    if (filterType !== 'all') {
      result = result.filter((o) => o.type === filterType);
    }

    // Filter by time range
    if (filterDays > 0) {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - filterDays);
      result = result.filter((o) => new Date(o.created_at) >= cutoff);
    }

    // Sort: most recent first
    result.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    return result;
  }, [orders, filterType, filterDays]);

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-8 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
          Inventario
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Historial de Entradas y Salidas
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Consulta todas las entradas y salidas registradas en el inventario, ordenadas de más reciente a más antigua.
        </p>
      </section>

      {/* Filters */}
      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          {/* Type filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">Tipo:</span>
            <div className="flex rounded-lg border border-slate-300 overflow-hidden">
              {(['all', 'entry', 'exit'] as const).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setFilterType(type)}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    filterType === type
                      ? 'bg-brand text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {type === 'all' ? 'Todas' : type === 'entry' ? 'Solo entradas' : 'Solo salidas'}
                </button>
              ))}
            </div>
          </div>

          {/* Time filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-700">Período:</span>
            <div className="flex rounded-lg border border-slate-300 overflow-hidden">
              {TIME_RANGES.map((range) => (
                <button
                  key={range.value}
                  type="button"
                  onClick={() => setFilterDays(range.value)}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    filterDays === range.value
                      ? 'bg-brand text-white'
                      : 'bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {range.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Content */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand border-t-transparent" />
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && filteredOrders.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
          {orders.length === 0
            ? 'No hay entradas ni salidas registradas en el inventario.'
            : 'No se encontraron movimientos con los filtros seleccionados.'}
        </div>
      )}

      {!loading && !error && filteredOrders.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase text-slate-600">
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Producto</th>
                <th className="px-4 py-3">SKU</th>
                <th className="px-4 py-3">Cantidad</th>
                <th className="px-4 py-3">Oficina</th>
                <th className="px-4 py-3">Usuario</th>
                <th className="px-4 py-3">Detalle</th>
                <th className="px-4 py-3">Fecha</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredOrders.map((order) => (
                <tr
                  key={`${order.type}-${order.id}`}
                  className="transition-colors hover:bg-slate-50"
                >
                  {/* Type badge */}
                  <td className="px-4 py-3">
                    {order.type === 'entry' ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m0 0l-6-6m6 6l6-6" />
                        </svg>
                        Entrada
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full border border-red-300 bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 19.5v-15m0 0l-6 6m6-6l6 6" />
                        </svg>
                        Salida
                      </span>
                    )}
                  </td>

                  {/* Product */}
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {order.asset_name}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{order.asset_sku}</td>

                  {/* Quantity */}
                  <td className="px-4 py-3">
                    <span
                      className={`font-semibold ${
                        order.type === 'entry' ? 'text-emerald-600' : 'text-red-600'
                      }`}
                    >
                      {order.type === 'entry' ? '+' : '-'}
                      {order.quantity}
                    </span>
                  </td>

                  {/* Office */}
                  <td className="px-4 py-3 text-slate-600">{order.office}</td>

                  {/* User */}
                  <td className="px-4 py-3">
                    <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                      {order.user_uuid}
                    </code>
                  </td>

                  {/* Detail */}
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {order.type === 'entry' ? (
                      <span>Proveedor: {order.supplier}</span>
                    ) : (
                      <span>
                        {order.exit_type === 'allocation'
                          ? `Asignado a: ${order.assigned_to || '—'}`
                          : 'Consumo'}
                      </span>
                    )}
                  </td>

                  {/* Date */}
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                    {formatDate(order.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}