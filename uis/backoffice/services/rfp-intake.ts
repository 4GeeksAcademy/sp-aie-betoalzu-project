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

export async function generateRfpResponses(
  ticketId: string,
): Promise<RfpTicketSummary> {
  const response = await fetch(
    `/api/rfp-intake/tickets/${encodeURIComponent(ticketId)}/generate`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudieron generar las secciones.'));
  }
  return (await response.json()) as RfpTicketSummary;
}

export async function startRfpApprovals(
  ticketId: string,
): Promise<RfpTicketSummary> {
  const response = await fetch(
    `/api/rfp-intake/tickets/${encodeURIComponent(ticketId)}/approvals/start`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudieron iniciar las aprobaciones.'));
  }
  return (await response.json()) as RfpTicketSummary;
}

export type RfpApprovalAction = 'approve' | 'reject' | 'request_changes';

export async function decideRfpApproval(
  ticketId: string,
  departmentId: string,
  decision: {
    action: RfpApprovalAction;
    draft_sha256: string;
    draft_version: number;
    comment?: string;
  },
): Promise<void> {
  const response = await fetch(
    `/api/rfp-intake/tickets/${encodeURIComponent(ticketId)}/approvals/${encodeURIComponent(departmentId)}/decision`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(decision),
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudo registrar la decisión.'));
  }
}

export async function resumeRfpApprovalRevision(
  ticketId: string,
  departmentId: string,
): Promise<RfpTicketSummary> {
  const response = await fetch(
    `/api/rfp-intake/tickets/${encodeURIComponent(ticketId)}/approvals/${encodeURIComponent(departmentId)}/resume`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudo reanudar la revisión.'));
  }
  return (await response.json()) as RfpTicketSummary;
}

export async function downloadFinalRfpDocument(ticketId: string): Promise<Blob> {
  const response = await fetch(
    `/api/rfp-intake/tickets/${encodeURIComponent(ticketId)}/final-document`,
    {
      headers: getAuthHeaders(),
      cache: 'no-store',
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, 'No se pudo descargar el documento final.'));
  }
  return response.blob();
}
