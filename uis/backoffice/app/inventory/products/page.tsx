'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchProducts } from '@/lib/inventory';
import { getStoredToken } from '@/lib/auth-token';
import type { Product } from '@/types/inventory';
import { ASSET_CATEGORY_LABELS, type AssetCategory } from '@/types/inventory';

const STOCK_LOW_THRESHOLD = 5;

function categoryBadgeClass(category: string) {
  const classes: Record<string, string> = {
    hardware: 'bg-purple-100 text-purple-800',
    peripherals: 'bg-cyan-100 text-cyan-800',
    office_supplies: 'bg-orange-100 text-orange-800',
    training_materials: 'bg-green-100 text-green-800',
  };
  return classes[category] || 'bg-slate-100 text-slate-800';
}

function stockBadgeClass(stock: number) {
  if (stock <= 0) return 'bg-red-100 text-red-800 border-red-300';
  if (stock <= STOCK_LOW_THRESHOLD) return 'bg-amber-100 text-amber-800 border-amber-300';
  return 'bg-emerald-100 text-emerald-800 border-emerald-300';
}

function stockLabel(stock: number) {
  if (stock <= 0) return 'Sin stock';
  if (stock <= STOCK_LOW_THRESHOLD) return 'Stock bajo';
  return 'Suficiente';
}

export default function InventoryProductsPage() {
  const router = useRouter();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.push('/login?from=/inventory/products');
      return;
    }

    loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadProducts() {
    setLoading(true);
    setError('');
    try {
      const data = await fetchProducts();
      setProducts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar el inventario.');
    } finally {
      setLoading(false);
    }
  }

  // Sort products alphabetically by name
  const sortedProducts = useMemo(
    () => [...products].sort((a, b) => a.name.localeCompare(b.name)),
    [products],
  );

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-8 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
          Inventario
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Stock de Productos
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Listado completo de todos los activos y productos disponibles, con su cantidad actual en stock.
        </p>

        {/* Navigation buttons */}
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => router.push('/inventory/orders/outbound')}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Formulario de Salida
          </button>
          <button
            type="button"
            onClick={() => router.push('/inventory/orders')}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500/50"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Historial de Entradas y Salidas
          </button>
        </div>
      </section>

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

      {!loading && !error && products.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
          No hay productos registrados en el inventario.
        </div>
      )}

      {!loading && !error && products.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-600">
              <tr>
                <th scope="col" className="px-5 py-3">Producto</th>
                <th scope="col" className="px-5 py-3">SKU</th>
                <th scope="col" className="px-5 py-3">Categoría</th>
                <th scope="col" className="px-5 py-3">Oficina</th>
                <th scope="col" className="px-5 py-3">Stock</th>
                <th scope="col" className="px-5 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sortedProducts.map((product) => (
                <tr key={product.id} className="transition-colors hover:bg-slate-50/60">
                  <td className="px-5 py-4 font-medium text-slate-900">{product.name}</td>
                  <td className="px-5 py-4 text-slate-500">{product.sku}</td>
                  <td className="px-5 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${categoryBadgeClass(product.category)}`}>
                      {ASSET_CATEGORY_LABELS[product.category as AssetCategory] || product.category}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-slate-600">{product.office}</td>
                  <td className="px-5 py-4">
                    <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${stockBadgeClass(product.current_stock)}`}>
                      {product.current_stock} uds. — {stockLabel(product.current_stock)}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          router.push(`/inventory/orders/inbound?asset_id=${product.id}&name=${encodeURIComponent(product.name)}`)
                        }
                        className="inline-flex items-center rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                      >
                        Entrada
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          router.push(`/inventory/orders/outbound?asset_id=${product.id}&name=${encodeURIComponent(product.name)}`)
                        }
                        className="inline-flex items-center rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                      >
                        Salida
                      </button>
                    </div>
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