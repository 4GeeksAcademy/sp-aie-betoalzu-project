import { Candidate, Note, CandidateForm } from '../types/candidate';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

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
  if (!API_URL) throw new Error('Falta NEXT_PUBLIC_API_URL en la configuración');
  return API_URL;
}

function extractCandidateList(data: any): CandidateApi[] {
  if (Array.isArray(data)) return data as CandidateApi[];
  if (Array.isArray(data?.results)) return data.results as CandidateApi[];
  if (Array.isArray(data?.data)) return data.data as CandidateApi[];
  return [];
}

export async function getCandidates(params?: Record<string, string>) {
  if (params) {
    const query = '?' + new URLSearchParams(params).toString();
    const res = await fetch(`${getApiUrl()}/records${query}`, { cache: 'no-store' });
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
    const res = await fetch(`${getApiUrl()}/records?${query}`, { cache: 'no-store' });
    const data = await handleResponse(res);
    const pageItems = extractCandidateList(data);

    if (!pageItems.length) break;

    all.push(...pageItems);
    total = typeof data?.total === 'number' ? data.total : all.length;
    page += 1;

    if (page > 50) break;
  }

  return all
    .map((item) => normalizeCandidate(item))
    .sort((a, b) => new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime());
}

export async function getCandidate(id: string) {
  const res = await fetch(`${getApiUrl()}/records/${id}`, { cache: 'no-store' });
  const data = await handleResponse(res);
  return normalizeCandidate(data as CandidateApi);
}

export async function createCandidate(data: CandidateForm) {
  const res = await fetch(`${getApiUrl()}/records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toApiPayload(data)),
  });
  const response = await handleResponse(res);
  return normalizeCandidate(response as CandidateApi);
}

export async function updateCandidate(id: string, data: Partial<CandidateForm>) {
  const res = await fetch(`${getApiUrl()}/records/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toApiPayload(data)),
  });
  const response = await handleResponse(res);
  return normalizeCandidate(response as CandidateApi);
}

export async function patchCandidate(id: string, data: Partial<CandidateForm>) {
  const res = await fetch(`${getApiUrl()}/records/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toApiPayload(data)),
  });
  const response = await handleResponse(res);
  return normalizeCandidate(response as CandidateApi);
}

export async function getNotes(candidateId: string) {
  const res = await fetch(`${getApiUrl()}/records/${candidateId}/notes`, { cache: 'no-store' });
  const data = await handleResponse(res);
  if (Array.isArray(data)) return data as Note[];
  if (Array.isArray(data.results)) return data.results as Note[];
  if (Array.isArray(data.data)) return data.data as Note[];
  return [];
}

export async function addNote(candidateId: string, content: string) {
  const res = await fetch(`${getApiUrl()}/records/${candidateId}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  return handleResponse(res) as Promise<Note>;
}

export async function deleteNote(candidateId: string, noteId: string) {
  const res = await fetch(`${getApiUrl()}/records/${candidateId}/notes/${noteId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Error al eliminar la nota');
}
