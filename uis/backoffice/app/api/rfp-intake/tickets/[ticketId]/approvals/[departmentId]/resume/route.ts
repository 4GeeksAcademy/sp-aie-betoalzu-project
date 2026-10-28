import { proxyToBackend } from '@/lib/backend-proxy';

type RouteContext = {
  params: Promise<{ ticketId: string; departmentId: string }>;
};

export async function POST(request: Request, { params }: RouteContext) {
  const authHeader = request.headers.get('authorization') || '';
  const { ticketId, departmentId } = await params;

  return proxyToBackend({
    path: `/rfp-intake/tickets/${encodeURIComponent(ticketId)}/approvals/${encodeURIComponent(departmentId)}/resume`,
    init: {
      method: 'POST',
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    label: 'reanudación de revisión RFP',
    forwardAuth: true,
  });
}
