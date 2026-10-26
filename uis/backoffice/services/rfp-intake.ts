import { getAuthHeaders } from '@/lib/auth-token';
import type { RfpTicketDetail, RfpTicketSummary } from '@/types/rfp-intake';

async function readError(response: Response, fallback: string): Promise<string> {
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string | { message?: string };
    error?: string;
  };
  if (typeof payload.detail === 'string') return payload.detail;
  if (payload.detail?.message) return payload.detail.message;
  return payload.error || fallback;
}

export async function listRfpTickets(): Promise<RfpTicketSummary[]> {
  const response = await fetch('/api/rfp-intake/tickets', {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudieron cargar los tickets.'));
  }
  return (await response.json()) as RfpTicketSummary[];
}

export async function getRfpTicket(ticketId: string): Promise<RfpTicketDetail> {
  const response = await fetch(`/api/rfp-intake/tickets/${encodeURIComponent(ticketId)}`, {
    headers: getAuthHeaders(),
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudo consultar el ticket.'));
  }
  return (await response.json()) as RfpTicketDetail;
}

export async function uploadRfp(file: File): Promise<RfpTicketSummary> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch('/api/rfp-intake/tickets', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudo cargar el PDF.'));
  }
  return (await response.json()) as RfpTicketSummary;
}

export async function retryRfpTicket(ticketId: string): Promise<RfpTicketSummary> {
  const response = await fetch(
    `/api/rfp-intake/tickets/${encodeURIComponent(ticketId)}/retry`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudo reintentar el análisis.'));
  }
  return (await response.json()) as RfpTicketSummary;
}
