import { proxyToBackend } from '@/lib/backend-proxy';

type RouteContext = { params: Promise<{ ticketId: string }> };

export async function POST(request: Request, { params }: RouteContext) {
  const authHeader = request.headers.get('authorization') || '';
  const { ticketId } = await params;

  return proxyToBackend({
    path: `/rfp-intake/tickets/${encodeURIComponent(ticketId)}/retry`,
    init: {
      method: 'POST',
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    label: 'reintento de análisis RFP',
    forwardAuth: true,
  });
}
