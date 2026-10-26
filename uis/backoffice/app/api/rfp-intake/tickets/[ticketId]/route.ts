import { proxyToBackend } from '@/lib/backend-proxy';

type RouteContext = { params: Promise<{ ticketId: string }> };

export async function GET(request: Request, { params }: RouteContext) {
  const authHeader = request.headers.get('authorization') || '';
  const { ticketId } = await params;

  return proxyToBackend({
    path: `/rfp-intake/tickets/${encodeURIComponent(ticketId)}`,
    init: {
      method: 'GET',
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    label: 'ticket RFP',
    forwardAuth: true,
  });
}
