import dynamic from 'next/dynamic';
import { cookies } from 'next/headers';
import { Supplier } from '@/types/supplier';

const SuppliersManagerClient = dynamic(
  () => import('@/components/SuppliersManagerClient'),
  { loading: () => <p className="text-sm text-slate-500">Cargando gestor de proveedores...</p> },
);

async function loadInitialSuppliers(): Promise<{ suppliers: Supplier[]; error: string }> {
  const apiUrl = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
  if (!apiUrl) {
    return {
      suppliers: [],
      error: 'No se configuro API_URL o NEXT_PUBLIC_API_URL para conectar con proveedores.',
    };
  }

  // Forward the auth token from the request cookie so the backend can authenticate
  let authHeader: Record<string, string> = {};
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get('nexova_token')?.value;
    if (token) {
      authHeader = { Authorization: `Bearer ${token}` };
    }
  } catch {
    // cookies() no disponible en este contexto; se cargará desde el cliente
  }

  try {
    const response = await fetch(`${apiUrl}/suppliers`, {
      cache: 'no-store',
      headers: { ...authHeader },
    });
    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const message =
        typeof payload === 'string'
          ? payload
          : payload?.detail || payload?.message || payload?.error || 'Error al cargar proveedores';
      return { suppliers: [], error: `${message} (HTTP ${response.status})` };
    }

    return { suppliers: Array.isArray(payload) ? (payload as Supplier[]) : [], error: '' };
  } catch (error) {
    return {
      suppliers: [],
      error: error instanceof Error ? error.message : 'No fue posible consultar proveedores.',
    };
  }
}

export default async function SuppliersPage() {
  const { suppliers, error } = await loadInitialSuppliers();

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <section className="mb-8 rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl shadow-slate-200/60 sm:p-8">
        <p className="mb-2 inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand">
          Compras y Proveedores
        </p>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">Gestion de Proveedores</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 sm:text-base">
          Administra alta, edicion, suspension y eliminacion de proveedores conectados al API de operaciones.
        </p>
      </section>

      <SuppliersManagerClient initialSuppliers={suppliers} initialError={error} />
    </main>
  );
}
