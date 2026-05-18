import { Candidate, Note, CandidateForm } from '../types/candidate';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

function handleResponse(res: Response) {
  if (!res.ok) throw new Error('Error en la petición');
  return res.json();
}

export async function getCandidates(params?: Record<string, string>) {
  const query = params ? '?' + new URLSearchParams(params).toString() : '';
  const res = await fetch(`${API_URL}/records${query}`);
  const data = await handleResponse(res);
  // Ajusta aquí según la estructura real de la API
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  if (Array.isArray(data.data)) return data.data;
  throw new Error('Formato inesperado de respuesta de la API');
}

export async function getCandidate(id: string) {
  const res = await fetch(`${API_URL}/records/${id}`);
  return handleResponse(res) as Promise<Candidate>;
}

export async function createCandidate(data: CandidateForm) {
  const res = await fetch(`${API_URL}/records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res) as Promise<Candidate>;
}

export async function updateCandidate(id: string, data: Partial<CandidateForm>) {
  const res = await fetch(`${API_URL}/records/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res) as Promise<Candidate>;
}

export async function patchCandidate(id: string, data: Partial<CandidateForm>) {
  const res = await fetch(`${API_URL}/records/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(res) as Promise<Candidate>;
}

export async function getNotes(candidateId: string) {
  const res = await fetch(`${API_URL}/records/${candidateId}/notes`);
  return handleResponse(res) as Promise<Note[]>;
}

export async function addNote(candidateId: string, content: string) {
  const res = await fetch(`${API_URL}/records/${candidateId}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  return handleResponse(res) as Promise<Note>;
}

export async function deleteNote(candidateId: string, noteId: string) {
  const res = await fetch(`${API_URL}/records/${candidateId}/notes/${noteId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Error al eliminar la nota');
}
