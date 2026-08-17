import { proxyToIncidentBackend } from '../_shared';

export async function GET(request: Request) {
  const authHeader = request.headers.get('authorization') || '';
  return proxyToIncidentBackend('/api/incidents/summary', {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}