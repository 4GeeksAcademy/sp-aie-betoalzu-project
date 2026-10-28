import { proxyToBackend } from '@/lib/backend-proxy';

type RouteContext = {
  params: Promise<{ ticketId: string; departmentId: string }>;
};

export async function POST(request: Request, { params }: RouteContext) {
  const authHeader = request.headers.get('authorization') || '';
  const { ticketId, departmentId } = await params;
  const body = await request.text();

  return proxyToBackend({
    path: `/rfp-intake/tickets/${encodeURIComponent(ticketId)}/approvals/${encodeURIComponent(departmentId)}/decision`,
    init: {
      method: 'POST',
      headers: authHeader ? { Authorization: authHeader } : {},
      body,
    },
    label: 'decisión de aprobación RFP',
    forwardAuth: true,
  });
}
