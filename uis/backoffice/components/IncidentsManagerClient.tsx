'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  INCIDENT_STATUSES,
  INCIDENT_CATEGORIES,
  INCIDENT_ORIGINS,
  INCIDENT_BRANCHES,
  Incident,
  IncidentInput,
  IncidentSummary,
} from '@/types/incident';
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_CATEGORY_LABELS,
  INCIDENT_ORIGIN_LABELS,
  INCIDENT_BRANCH_LABELS,
} from '@/types/labels';
import {
  getIncidents,
  createIncident,
  updateIncident,
  updateIncidentStatus,
  deleteIncident,
  getIncidentsSummary,
  seedIncidentsFromCsv,
} from '@/services/api';

const INITIAL_FORM: IncidentInput = {
  title: '',
  description: '',
  category: 'technical_failure',
  origin: 'customer',
  branch: 'central',
  reported_by: '',
  assigned_to: '',
};

const STATUS_BADGE: Record<string, string> = {
  open: 'border-amber-300 bg-amber-50 text-amber-800',
  in_progress: 'border-blue-300 bg-blue-50 text-blue-800',
  resolved: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  discarded: 'border-slate-300 bg-slate-50 text-slate-600',
};

function formatDate(value: string | null) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
}

function statusBadgeClass(status: string) {
  return STATUS_BADGE[status] || 'border-slate-300 bg-slate-50 text-slate-600';
}

export default function IncidentsManagerClient() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<IncidentInput>(INITIAL_FORM);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [seedMessage, setSeedMessage] = useState('');

  async function loadData() {
    setLoading(true);
    setError('');
    try {
      const [incidentsData, summaryData] = await Promise.all([
        getIncidents({
          status: filterStatus || undefined,
          category: filterCategory || undefined,
        }),
        getIncidentsSummary(),
      ]);
      setIncidents(incidentsData);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar incidencias.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStatus, filterCategory]);

  const sortedIncidents = useMemo(
    () =>
      [...incidents].sort((a, b) => {
        const order = ['open', 'in_progress', 'resolved', 'discarded'];
        const aIdx = order.indexOf(a.status);
        const bIdx = order.indexOf(b.status);
        if (aIdx !== bIdx) return aIdx - bIdx;
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }),
    [incidents],
  );

  function resetForm() {
    setEditingId(null);
    setForm(INITIAL_FORM);
    setFormError('');
  }

  function onEdit(incident: Incident) {
    setEditingId(incident.id);
    setFormError('');
    setForm({
      title: incident.title,
      description: incident.description || '',
      category: incident.category as IncidentInput['category'],
      origin: incident.origin as IncidentInput['origin'],
      branch: incident.branch as IncidentInput['branch'],
      reported_by: incident.reported_by || '',
      assigned_to: incident.assigned_to || '',
    });
  }

  function validateForm() {
    if (!form.title.trim()) return 'El titulo es obligatorio.';
    return '';
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError('');
    setError('');

    const validationError = validateForm();
    if (validationError) {
      setFormError(validationError);
      return;
    }

    setSubmitting(true);
    try {
      const payload: IncidentInput = {
        ...form,
        title: form.title.trim(),
        description: form.description?.trim() || null,
        reported_by: form.reported_by?.trim() || null,
        assigned_to: form.assigned_to?.trim() || null,
      };

      if (editingId) {
        await updateIncident(editingId, payload);
      } else {
        await createIncident(payload);
      }

      resetForm();
      await loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Error al guardar la incidencia.');
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete(incident: Incident) {
    if (!window.confirm(`Eliminar incidencia #${incident.id}: "${incident.title}"?`)) return;
    setError('');
    try {
      await deleteIncident(incident.id);
      setIncidents((prev) => prev.filter((i) => i.id !== incident.id));
      if (editingId === incident.id) resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al eliminar.');
    }
  }

  async function onTransition(incident: Incident, nextStatus: string) {
    setError('');
    try {
      const updated = await updateIncidentStatus(incident.id, nextStatus as Incident['status']);
      setIncidents((prev) => prev.map((i) => (i.id === incident.id ? updated : i)));
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cambiar estado.');
    }
  }

  async function handleSeed() {
    if (!window.confirm('¿Cargar datos historicos desde incidents-nexova.csv? Se eliminaran los datos actuales primero.')) return;
    setSeedMessage('');
    setError('');
    try {
      const result = await seedIncidentsFromCsv();
      setSeedMessage(`Seed completado: ${result.inserted} incidencias insertadas.`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error en seed.');
    }
  }

  const nextStatusMap: Record<string, string[]> = {
    open: ['in_progress', 'discarded'],
    in_progress: ['resolved', 'discarded'],
    resolved: [],
    discarded: [],
  };

  const summaryCards = summary
    ? [
        { label: 'Total', value: summary.total, color: 'bg-slate-900' },
        { label: 'Abiertas', value: summary.by_status.open || 0, color: 'bg-amber-500' },
        { label: 'En progreso', value: summary.by_status.in_progress || 0, color: 'bg-blue-500' },
        { label: 'Resueltas', value: summary.by_status.resolved || 0, color: 'bg-emerald-500' },
        { label: 'Descartadas', value: summary.by_status.discarded || 0, color: 'bg-slate-400' },
        { label: 'Críticas (SLA)', value: summary.open_critical_count, color: 'bg-rose-600' },
      ]
    : [];

  return (
    <section className="space-y-6">
      {error && (
        <div className="flex items-center justify-between rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          <div>
            <p className="font-semibold">Error</p>
            <p className="mt-1">{error}</p>
          </div>
          <button
            onClick={loadData}
            className="ml-4 shrink-0 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-100"
          >
            Reintentar
          </button>
        </div>
      )}

      {seedMessage && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {seedMessage}
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {summaryCards.map((card) => (
            <div key={card.label} className="surface-card flex items-center gap-3 p-4">
              <div className={`h-10 w-10 rounded-xl ${card.color} flex items-center justify-center text-lg font-bold text-white`}>
                {card.value}
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">{card.label}</p>
                <p className="text-lg font-bold text-slate-900">{card.value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Todos los estados</option>
          {INCIDENT_STATUSES.map((s) => (
            <option key={s} value={s}>{INCIDENT_STATUS_LABELS[s]}</option>
          ))}
        </select>

        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Todas las categorías</option>
          {INCIDENT_CATEGORIES.map((c) => (
            <option key={c} value={c}>{INCIDENT_CATEGORY_LABELS[c]}</option>
          ))}
        </select>

        <button type="button" onClick={handleSeed} className="btn-secondary text-sm">
          + Cargar datos históricos (CSV)
        </button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[400px_1fr]">
        {/* Form */}
        <article className="surface-card h-fit p-6">
          <h2 className="text-xl font-bold text-slate-900">
            {editingId ? 'Editar incidencia' : 'Nueva incidencia'}
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {editingId ? 'Actualiza los campos necesarios.' : 'Registra una nueva incidencia en el sistema.'}
          </p>

          {formError && (
            <div className="mt-3 rounded-xl border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              {formError}
            </div>
          )}

          <form className="mt-5 space-y-4" onSubmit={onSubmit}>
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Título *</span>
              <input
                value={form.title}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                placeholder="Ej: Error en sincronización de ATS"
                required
                maxLength={120}
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Descripción</span>
              <textarea
                value={form.description || ''}
                onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                rows={3}
                placeholder="Describe el problema con detalle..."
              />
            </label>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700">Categoría</span>
                <select
                  value={form.category}
                  onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value as IncidentInput['category'] }))}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                >
                  {INCIDENT_CATEGORIES.map((c) => (
                    <option key={c} value={c}>{INCIDENT_CATEGORY_LABELS[c]}</option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700">Origen</span>
                <select
                  value={form.origin}
                  onChange={(e) => setForm((prev) => ({ ...prev, origin: e.target.value as IncidentInput['origin'] }))}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                >
                  {INCIDENT_ORIGINS.map((o) => (
                    <option key={o} value={o}>{INCIDENT_ORIGIN_LABELS[o]}</option>
                  ))}
                </select>
              </label>
            </div>

            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-slate-700">Oficina / Sede</span>
              <select
                value={form.branch}
                onChange={(e) => setForm((prev) => ({ ...prev, branch: e.target.value as IncidentInput['branch'] }))}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
              >
                {INCIDENT_BRANCHES.map((b) => (
                  <option key={b} value={b}>{INCIDENT_BRANCH_LABELS[b]}</option>
                ))}
              </select>
            </label>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700">Reportado por</span>
                <input
                  value={form.reported_by || ''}
                  onChange={(e) => setForm((prev) => ({ ...prev, reported_by: e.target.value }))}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Nombre o email"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-slate-700">Asignado a</span>
                <input
                  value={form.assigned_to || ''}
                  onChange={(e) => setForm((prev) => ({ ...prev, assigned_to: e.target.value }))}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Nombre o equipo"
                />
              </label>
            </div>

            <div className="flex gap-2">
              <button type="submit" disabled={submitting} className="btn-primary flex-1">
                {submitting ? 'Guardando...' : editingId ? 'Actualizar' : 'Crear incidencia'}
              </button>
              {editingId && (
                <button type="button" onClick={resetForm} className="btn-secondary">
                  Cancelar
                </button>
              )}
            </div>
          </form>
        </article>

        {/* Table */}
        <article className="surface-card overflow-hidden p-6">
          <h2 className="text-xl font-bold text-slate-900">
            Incidencias {loading ? '(cargando...)' : `(${incidents.length})`}
          </h2>

          {loading ? (
            <p className="mt-4 text-sm text-slate-500">Cargando incidencias...</p>
          ) : sortedIncidents.length === 0 ? (
            <div className="mt-8 text-center">
              <p className="text-lg font-medium text-slate-400">No hay incidencias</p>
              <p className="text-sm text-slate-400">Usa el formulario para crear la primera.</p>
            </div>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
                    <th className="py-3 pr-4">ID</th>
                    <th className="py-3 pr-4">Título</th>
                    <th className="py-3 pr-4">Estado</th>
                    <th className="py-3 pr-4">Categoría</th>
                    <th className="py-3 pr-4">Origen</th>
                    <th className="py-3 pr-4">Sede</th>
                    <th className="py-3 pr-4">Creada</th>
                    <th className="py-3 pr-4">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedIncidents.map((inc) => (
                    <tr key={inc.id} className="border-b border-slate-100 transition-colors hover:bg-slate-50">
                      <td className="py-3 pr-4 font-mono text-xs text-slate-500">#{inc.id}</td>
                      <td className="py-3 pr-4">
                        <button
                          onClick={() => onEdit(inc)}
                          className="text-left font-medium text-slate-900 hover:text-brand"
                          title="Editar"
                        >
                          {inc.title}
                        </button>
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusBadgeClass(inc.status)}`}>
                          {INCIDENT_STATUS_LABELS[inc.status] || inc.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {INCIDENT_CATEGORY_LABELS[inc.category] || inc.category}
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {INCIDENT_ORIGIN_LABELS[inc.origin] || inc.origin}
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {INCIDENT_BRANCH_LABELS[inc.branch] || inc.branch}
                      </td>
                      <td className="py-3 pr-4 whitespace-nowrap text-xs text-slate-400">
                        {formatDate(inc.created_at)}
                      </td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-1">
                          {nextStatusMap[inc.status]?.map((next) => (
                            <button
                              key={next}
                              onClick={() => onTransition(inc, next)}
                              className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100"
                              title={`Cambiar a ${INCIDENT_STATUS_LABELS[next]}`}
                            >
                              {INCIDENT_STATUS_LABELS[next]}
                            </button>
                          ))}
                          <button
                            onClick={() => onDelete(inc)}
                            className="rounded-lg border border-transparent px-2 py-1 text-xs font-medium text-rose-500 transition-colors hover:bg-rose-50"
                            title="Eliminar"
                          >
                            ✕
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

      {/* Category breakdown */}
      {summary && (
        <article className="surface-card p-6">
          <h3 className="text-lg font-bold text-slate-900">Desglose por categoría</h3>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {INCIDENT_CATEGORIES.map((cat) => (
              <div key={cat} className="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
                <p className="text-xs font-medium text-slate-500">{INCIDENT_CATEGORY_LABELS[cat]}</p>
                <p className="text-2xl font-bold text-slate-900">{summary.by_category[cat] || 0}</p>
              </div>
            ))}
          </div>
        </article>
      )}
    </section>
  );
}