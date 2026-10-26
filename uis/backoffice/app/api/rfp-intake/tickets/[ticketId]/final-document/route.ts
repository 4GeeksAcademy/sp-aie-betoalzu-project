import { proxyToBackend } from '@/lib/backend-proxy';

type RouteContext = { params: Promise<{ ticketId: string }> };

export async function GET(request: Request, { params }: RouteContext) {
  const authHeader = request.headers.get('authorization') || '';
  const { ticketId } = await params;

  return proxyToBackend({
    path: `/rfp-intake/tickets/${encodeURIComponent(ticketId)}/final-document`,
    init: {
      method: 'GET',
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    label: 'documento final RFP',
    forwardAuth: true,
  });
}
