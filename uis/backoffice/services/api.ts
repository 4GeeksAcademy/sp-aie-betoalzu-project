import { Candidate, Note, CandidateForm } from '../types/candidate';
import { Supplier, SupplierInput } from '../types/supplier';
import { getAuthHeaders } from '../lib/auth-token';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export type IncidentInvalidRules = {
  missing_client_company: number;
  invalid_category: number;
  invalid_description: number;
  invalid_agent: number;
  invalid_status: number;
  invalid_email: number;
  closed_no_score: number;
  score_out_of_range: number;
};

export type CsvIncidentSummary = {
  source_file: string;
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_rules: IncidentInvalidRules;
  categories: Record<string, number>;
  statuses: Record<string, number>;
  scores: Record<string, number>;
  closed_tickets: number;
  scored_tickets: number;
  average_score: number;
};

type CandidateApi = Omit<Candidate, 'linkedin'> & {
  linkedin?: string | null;
  linkedin_url?: string | null;
};

function normalizeCandidate(candidate: CandidateApi): Candidate {
  return {
    ...candidate,
    linkedin: candidate.linkedin ?? candidate.linkedin_url ?? '',
  };
}

function toApiPayload(data: CandidateForm | Partial<CandidateForm>) {
  const { linkedin, ...rest } = data;
  return {
    ...rest,
    ...(linkedin !== undefined ? { linkedin_url: linkedin } : {}),
  };
}

async function handleResponse(res: Response) {
  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    const message =
      typeof payload === 'string'
        ? payload
        : payload?.detail || payload?.message || payload?.error || 'Error en la petición';
    throw new Error(`${message} (HTTP ${res.status})`);
  }

  return payload;
}

function getApiUrl() {
  // Fallback al mismo origen cuando el front y la API comparten host.
  return (API_URL || '').replace(/\/$/, '');
}

/** Merge default JSON headers with the current Authorization header. */
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...extra,
  };
}

function extractCandidateList(data: unknown): CandidateApi[] {
  if (Array.isArray(data)) return data as CandidateApi[];

  if (data && typeof data === 'object') {
    const payload = data as { results?: unknown; data?: unknown };
    if (Array.isArray(payload.results)) return payload.results as CandidateApi[];
    if (Array.isArray(payload.data)) return payload.data as CandidateApi[];
  }

  return [];
}

function extractTotalCount(data: unknown): number | null {
  if (!data || typeof data !== 'object') return null;
  const payload = data as { total?: unknown };
  return typeof payload.total === 'number' ? payload.total : null;
}

export async function getCandidates(params?: Record<string, string>) {
  if (params) {
    const query = '?' + new URLSearchParams(params).toString();
    const res = await fetch(`${getApiUrl()}/records${query}`, {
      cache: 'no-store',
      headers: authHeaders(),
    });
    const data = await handleResponse(res);
    const list = extractCandidateList(data);
    if (!list.length) throw new Error('Formato inesperado de respuesta de la API');
    return list
      .map((item) => normalizeCandidate(item))
      .sort((a, b) => new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime());
  }

  const pageSize = 100;
  let page = 1;
  let total = Number.POSITIVE_INFINITY;
  const all: CandidateApi[] = [];

  while (all.length < total) {
    const query = new URLSearchParams({ page: String(page), limit: String(pageSize) }).toString();
    const res = await fetch(`${getApiUrl()}/records?${query}`, {
      cache: 'no-store',
      headers: authHeaders(),
    });
    const data = await handleResponse(res);
    const pageItems = extractCandidateList(data);

    if (!pageItems.length) break;

    all.push(...pageItems);
    total = extractTotalCount(data) ?? all.length;
    page += 1;

    if (page > 50) break;
  }

  return all
    .map((item) => normalizeCandidate(item))
    .sort((a, b) => new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime());
}

export async function getCandidate(id: string) {
  const res = await fetch(`${getApiUrl()}/records/${id}`, {
    cache: 'no-store',
    headers: authHeaders(),
  });
  const data = await handleResponse(res);
  return normalizeCandidate(data as CandidateApi);
}

export async function createCandidate(data: CandidateForm) {
  const res = await fetch(`${getApiUrl()}/records`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(toApiPayload(data)),
  });
  const response = await handleResponse(res);
  return normalizeCandidate(response as CandidateApi);
}

export async function updateCandidate(id: string, data: Partial<CandidateForm>) {
  const res = await fetch(`${getApiUrl()}/records/${id}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(toApiPayload(data)),
  });
  const response = await handleResponse(res);
  return normalizeCandidate(response as CandidateApi);
}

export async function patchCandidate(id: string, data: Partial<CandidateForm>) {
  const res = await fetch(`${getApiUrl()}/records/${id}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(toApiPayload(data)),
  });
  const response = await handleResponse(res);
  return normalizeCandidate(response as CandidateApi);
}

export async function getNotes(candidateId: string) {
  const res = await fetch(`${getApiUrl()}/records/${candidateId}/notes`, {
    cache: 'no-store',
    headers: authHeaders(),
  });
  const data = await handleResponse(res);
  if (Array.isArray(data)) return data as Note[];
  if (Array.isArray(data.results)) return data.results as Note[];
  if (Array.isArray(data.data)) return data.data as Note[];
  return [];
}

export async function addNote(candidateId: string, content: string) {
  const res = await fetch(`${getApiUrl()}/records/${candidateId}/notes`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content }),
  });
  return handleResponse(res) as Promise<Note>;
}

export async function deleteNote(candidateId: string, noteId: string) {
  const res = await fetch(`${getApiUrl()}/records/${candidateId}/notes/${noteId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Error al eliminar la nota');
}

export async function analyzeIncidentsCsv(file: File) {
  const form = new FormData();
  form.append('file', file);

  const res = await fetch('/api/incidents/analyze', {
    method: 'POST',
    body: form,
  });

  return (await handleResponse(res)) as CsvIncidentSummary;
}

export async function exportIncidentResults() {
  const res = await fetch('/api/incidents/results/export', {
    method: 'GET',
    cache: 'no-store',
  });

  if (!res.ok) {
    const contentType = res.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const payload = isJson ? await res.json() : await res.text();
    const message =
      typeof payload === 'string'
        ? payload
        : payload?.detail || payload?.message || payload?.error || 'Error en la petición';
    throw new Error(`${message} (HTTP ${res.status})`);
  }

  const contentDisposition = res.headers.get('content-disposition') || '';
  const match = contentDisposition.match(/filename="?([^\"]+)"?/i);
  const fileName = match?.[1] || 'incident-metrics.csv';
  const blob = await res.blob();

  return { blob, fileName };
}

function normalizeSupplier(payload: Supplier): Supplier {
  return {
    ...payload,
    contract_renewal_date: payload.contract_renewal_date || null,
    contact_email: payload.contact_email || null,
    notes: payload.notes || null,
  };
}

function toSupplierPayload(data: SupplierInput) {
  return {
    ...data,
    contract_renewal_date: data.contract_renewal_date || null,
    contact_email: data.contact_email || null,
    notes: data.notes || null,
  };
}

export async function getSuppliers() {
  const res = await fetch('/api/suppliers', {
    cache: 'no-store',
    headers: authHeaders(),
  });
  const data = await handleResponse(res);
  if (!Array.isArray(data)) return [];

  return (data as Supplier[])
    .map((item) => normalizeSupplier(item))
    .sort((a, b) => a.name.localeCompare(b.name, 'es', { sensitivity: 'base' }));
}

export async function createSupplier(data: SupplierInput) {
  const res = await fetch('/api/suppliers', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(toSupplierPayload(data)),
  });

  const response = await handleResponse(res);
  return normalizeSupplier(response as Supplier);
}

export async function updateSupplier(id: number, data: Partial<SupplierInput>) {
  const res = await fetch(`/api/suppliers/${id}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });

  const response = await handleResponse(res);
  return normalizeSupplier(response as Supplier);
}

export async function updateSupplierStatus(id: number, status: Supplier['status']) {
  const res = await fetch(`/api/suppliers/${id}/status`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });

  const response = await handleResponse(res);
  return normalizeSupplier(response as Supplier);
}

export async function deleteSupplier(id: number) {
  const res = await fetch(`/api/suppliers/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });

  await handleResponse(res);
}

// ===========================================================================
// Incidents (Centralized Incident Manager)
// ===========================================================================

import type { Incident, IncidentInput, IncidentSummary } from '@/types/incident';

function normalizeIncident(payload: Incident): Incident {
  return {
    ...payload,
    description: payload.description || null,
    reported_by: payload.reported_by || null,
    assigned_to: payload.assigned_to || null,
    ticket_id: payload.ticket_id || null,
  };
}

export async function getIncidents(params?: { status?: string; category?: string; branch?: string; origin?: string }) {
  const query = params ? '?' + new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([_, v]) => v))).toString() : '';
  const res = await fetch(`/api/incidents${query}`, {
    cache: 'no-store',
    headers: authHeaders(),
  });
  const data = await handleResponse(res);
  if (!Array.isArray(data)) return [];
  return (data as Incident[]).map(normalizeIncident);
}

export async function getIncident(id: number) {
  const res = await fetch(`/api/incidents/${id}`, {
    cache: 'no-store',
    headers: authHeaders(),
  });
  const data = await handleResponse(res);
  return normalizeIncident(data as Incident);
}

export async function createIncident(data: IncidentInput) {
  const res = await fetch('/api/incidents', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  const response = await handleResponse(res);
  return normalizeIncident(response as Incident);
}

export async function updateIncident(id: number, data: Partial<IncidentInput>) {
  const res = await fetch(`/api/incidents/${id}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
  const response = await handleResponse(res);
  return normalizeIncident(response as Incident);
}

export async function updateIncidentStatus(id: number, status: Incident['status']) {
  const res = await fetch(`/api/incidents/${id}/status`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
  const response = await handleResponse(res);
  return normalizeIncident(response as Incident);
}

export async function deleteIncident(id: number) {
  const res = await fetch(`/api/incidents/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  await handleResponse(res);
}

export async function getIncidentsSummary() {
  const res = await fetch('/api/incidents/summary', {
    cache: 'no-store',
    headers: authHeaders(),
  });
  return (await handleResponse(res)) as IncidentSummary;
}

export async function seedIncidentsFromCsv() {
  const res = await fetch('/api/incidents/seed', {
    method: 'POST',
    headers: authHeaders(),
  });
  return handleResponse(res);
}
