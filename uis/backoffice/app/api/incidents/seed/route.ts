import { proxyToIncidentBackend } from '../_shared';

export async function POST(request: Request) {
  const authHeader = request.headers.get('authorization') || '';
  return proxyToIncidentBackend('/api/incidents/seed', {
    method: 'POST',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}