'use client';

import { useMemo, useState } from 'react';
import {
  SUPPLIER_CATEGORIES,
  SUPPLIER_CATEGORY_LABELS,
  SUPPLIER_COUNTRIES,
  SUPPLIER_COUNTRY_LABELS,
  SUPPLIER_STATUSES,
  SUPPLIER_STATUS_LABELS,
  Supplier,
  SupplierInput,
  SupplierStatus,
} from '@/types/supplier';
import { createSupplier, deleteSupplier, getSuppliers, updateSupplier, updateSupplierStatus } from '@/services/api';
import { useCrudForm } from '@/hooks/useCrudForm';

const INITIAL_FORM: SupplierInput = {
  name: '',
  country: 'Spain',
  categories: ['job_boards'],
  monthly_rate: 0,
  currency: 'EUR',
  status: 'active',
  contract_renewal_date: null,
  contact_email: null,
  notes: null,
};

function toCurrencyByCountry(country: SupplierInput['country']) {
  return country === 'Spain' ? 'EUR' : 'USD';
}

function formatDate(value: string | null) {
  if (!value) return 'No definido';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium' }).format(parsed);
}

function statusBadgeClass(status: SupplierStatus) {
  if (status === 'active') {
    return 'border-emerald-300 bg-emerald-50 text-emerald-800';
  }
  return 'border-rose-300 bg-rose-50 text-rose-800';
}

function preparePayload(form: SupplierInput): SupplierInput {
  return {
    ...form,
    name: form.name.trim(),
    contact_email: form.contact_email?.trim() || null,
    notes: form.notes?.trim() || null,
  };
}

type SuppliersManagerClientProps = {
  initialSuppliers: Supplier[];
  initialError?: string;
};

export default function SuppliersManagerClient({ initialSuppliers, initialError = '' }: SuppliersManagerClientProps) {
  const [suppliers, setSuppliers] = useState<Supplier[]>(initialSuppliers);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState(initialError);

  const crud = useCrudForm<SupplierInput, Supplier>({
    initialForm: INITIAL_FORM,
    createFn: (data) => createSupplier(preparePayload(data)),
    updateFn: (id, data) => updateSupplier(id, preparePayload(data)),
    deleteFn: deleteSupplier,
    loadData: loadSuppliers,
    validateForm: (form) => {
      if (!form.name.trim()) return 'El nombre es obligatorio.';
      if (form.categories.length === 0) return 'Debes seleccionar al menos una categoría.';
      if (!Number.isFinite(form.monthly_rate) || form.monthly_rate <= 0) {
        return 'La tarifa mensual debe ser mayor que 0.';
      }
      const expectedCurrency = toCurrencyByCountry(form.country);
      if (form.currency !== expectedCurrency) {
        return `La moneda para ${SUPPLIER_COUNTRY_LABELS[form.country]} debe ser ${expectedCurrency}.`;
      }
      return '';
    },
    mapEntityToForm: (supplier) => ({
      name: supplier.name,
      country: supplier.country,
      categories: supplier.categories,
      monthly_rate: supplier.monthly_rate,
      currency: supplier.currency,
      status: supplier.status,
      contract_renewal_date: supplier.contract_renewal_date,
      contact_email: supplier.contact_email,
      notes: supplier.notes,
    }),
    entityName: 'proveedor',
  });

  const sortedSuppliers = useMemo(
    () =>
      [...suppliers].sort((a, b) => {
        if (a.status === b.status) return a.name.localeCompare(b.name, 'es', { sensitivity: 'base' });
        return a.status === 'active' ? -1 : 1;
      }),
    [suppliers],
  );

  async function loadSuppliers() {
    setLoading(true);
    setPageError('');
    try {
      const data = await getSuppliers();
      setSuppliers(data);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : 'Error al cargar proveedores.');
    } finally {
      setLoading(false);
    }
  }

  function handleDelete(supplier: Supplier) {
    crud.onDelete(supplier, () => {
      setSuppliers((current) => current.filter((item) => item.id !== supplier.id));
    });
  }

  async function onToggleStatus(supplier: Supplier) {
    const nextStatus: SupplierStatus = supplier.status === 'active' ? 'suspended' : 'active';
    setPageError('');

    try {
      const updated = await updateSupplierStatus(supplier.id, nextStatus);
      setSuppliers((current) => current.map((item) => (item.id === supplier.id ? updated : item)));
    } catch (err) {
      setPageError(err instanceof Error ? err.message : 'No fue posible actualizar el estado.');
    }
  }

  return (
    <section className="space-y-6">
      {(pageError || crud.error) && (
        <div className="flex items-center justify-between rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          <div>
            <p className="font-semibold">Error de conexion o API</p>
            <p className="mt-1">{pageError || crud.error}</p>
          </div>
          <button
            onClick={loadSuppliers}
            className="ml-4 shrink-0 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-100"
          >
            Reintentar
          </button>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[380px_1fr]">
        <article className="surface-card p-6">
          <h2 className="text-xl font-bold text-slate-900">{crud.editingId ? 'Editar proveedor' : 'Nuevo proveedor'}</h2>
          <p className="mt-1 text-sm text-slate-600">Completa los campos para crear o actualizar el registro.</p>

          <form className="mt-5 space-y-4" onSubmit={crud.onSubmit}>
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Nombre</span>
              <input
                value={crud.form.name}
                onChange={(event) => crud.setForm((current) => ({ ...current, name: event.target.value }))}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Ej: LinkedIn Talent Solutions"
                required
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Pais</span>
              <select
                value={crud.form.country}
                onChange={(event) => {
                  const country = event.target.value as SupplierInput['country'];
                  crud.setForm((current) => ({ ...current, country, currency: toCurrencyByCountry(country) }));
                }}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                {SUPPLIER_COUNTRIES.map((country) => (
                  <option key={country} value={country}>
                    {SUPPLIER_COUNTRY_LABELS[country]}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Categoria(s)</span>
              <select
                multiple
                value={crud.form.categories}
                onChange={(event) => {
                  const selected = Array.from(event.target.selectedOptions).map((option) => option.value);
                  crud.setForm((current) => ({ ...current, categories: selected as SupplierInput['categories'] }));
                }}
                className="h-36 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                {SUPPLIER_CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {SUPPLIER_CATEGORY_LABELS[category]}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700">Tarifa mensual</span>
                <input
                  type="number"
                  min="1"
                  step="0.01"
                  value={crud.form.monthly_rate || ''}
                  onChange={(event) => {
                    const amount = Number(event.target.value);
                    crud.setForm((current) => ({ ...current, monthly_rate: Number.isFinite(amount) ? amount : 0 }));
                  }}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                  required
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700">Moneda</span>
                <select
                  value={crud.form.currency}
                  onChange={(event) =>
                    crud.setForm((current) => ({ ...current, currency: event.target.value as SupplierInput['currency'] }))
                  }
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="EUR">EUR</option>
                  <option value="USD">USD</option>
                </select>
              </label>
            </div>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Estado</span>
              <select
                value={crud.form.status}
                onChange={(event) =>
                  crud.setForm((current) => ({ ...current, status: event.target.value as SupplierInput['status'] }))
                }
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                {SUPPLIER_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {SUPPLIER_STATUS_LABELS[status]}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Renovacion de contrato</span>
              <input
                type="date"
                value={crud.form.contract_renewal_date || ''}
                onChange={(event) =>
                  crud.setForm((current) => ({
                    ...current,
                    contract_renewal_date: event.target.value ? event.target.value : null,
                  }))
                }
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Email de contacto</span>
              <input
                type="email"
                value={crud.form.contact_email || ''}
                onChange={(event) =>
                  crud.setForm((current) => ({ ...current, contact_email: event.target.value || null }))
                }
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="compras@proveedor.com"
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Notas</span>
              <textarea
                value={crud.form.notes || ''}
                onChange={(event) => crud.setForm((current) => ({ ...current, notes: event.target.value || null }))}
                rows={3}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Contexto comercial o detalles operativos"
              />
            </label>

            {crud.formError && (
              <div className="rounded-xl border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-900">{crud.formError}</div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={crud.submitting}
                className="inline-flex items-center justify-center rounded-full bg-brand px-5 py-2 text-sm font-bold text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-70"
              >
                {crud.submitting ? 'Guardando...' : crud.editingId ? 'Guardar cambios' : 'Crear proveedor'}
              </button>

              {crud.editingId && (
                <button
                  type="button"
                  onClick={crud.resetForm}
                  className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
                >
                  Cancelar edicion
                </button>
              )}
            </div>
          </form>
        </article>

        <article className="surface-card overflow-hidden">
          <header className="border-b border-slate-200 px-5 py-4 sm:px-6">
            <h2 className="text-xl font-bold text-slate-900">Listado de proveedores</h2>
            <p className="mt-1 text-sm text-slate-600">Total: {suppliers.length} registros en base de datos.</p>
          </header>

          {loading ? (
            <div className="p-6 text-sm text-slate-600">Cargando proveedores...</div>
          ) : suppliers.length === 0 ? (
            <div className="p-6 text-sm text-slate-600">No hay proveedores cargados actualmente.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-4 py-3">Nombre</th>
                    <th className="px-4 py-3">Pais</th>
                    <th className="px-4 py-3">Categorias</th>
                    <th className="px-4 py-3">Tarifa</th>
                    <th className="px-4 py-3">Estado</th>
                    <th className="px-4 py-3">Renovacion</th>
                    <th className="px-4 py-3">Contacto</th>
                    <th className="px-4 py-3">Notas</th>
                    <th className="px-4 py-3">Actualizado</th>
                    <th className="px-4 py-3">Acciones</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {sortedSuppliers.map((supplier) => (
                    <tr key={supplier.id}>
                      <td className="px-4 py-3 font-semibold text-slate-900">{supplier.name}</td>
                      <td className="px-4 py-3 text-slate-700">{SUPPLIER_COUNTRY_LABELS[supplier.country]}</td>
                      <td className="px-4 py-3 text-slate-700">
                        {supplier.categories.map((category) => SUPPLIER_CATEGORY_LABELS[category] || category).join(', ')}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {new Intl.NumberFormat('es-ES', {
                          style: 'currency',
                          currency: supplier.currency,
                          minimumFractionDigits: 2,
                        }).format(supplier.monthly_rate)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(supplier.status)}`}
                        >
                          {SUPPLIER_STATUS_LABELS[supplier.status]}
                        </span>
                        <button
                          type="button"
                          onClick={() => onToggleStatus(supplier)}
                          className="ml-2 inline-flex rounded-full border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                        >
                          {supplier.status === 'active' ? 'Suspender' : 'Activar'}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-slate-700">{formatDate(supplier.contract_renewal_date)}</td>
                      <td className="px-4 py-3 text-slate-700">{supplier.contact_email || 'No definido'}</td>
                      <td className="max-w-xs px-4 py-3 text-slate-700">{supplier.notes || 'Sin notas'}</td>
                      <td className="px-4 py-3 text-slate-700">{formatDate(supplier.updated_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => crud.onEdit(supplier)}
                            className="rounded-full border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                          >
                            Editar
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(supplier)}
                            className="rounded-full border border-rose-300 px-3 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-50"
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
