import { proxyToIncidentBackend } from '../../_shared';

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToIncidentBackend(`/api/incidents/${id}/status`, {
    method: 'PATCH',
    headers: authHeader ? { Authorization: authHeader } : {},
    body,
  });
}