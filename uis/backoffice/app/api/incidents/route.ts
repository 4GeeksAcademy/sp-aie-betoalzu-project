import { proxyToIncidentBackend } from './_shared';

export async function GET(request: Request) {
  const authHeader = request.headers.get('authorization') || '';
  return proxyToIncidentBackend('/api/incidents', {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

export async function POST(request: Request) {
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToIncidentBackend('/api/incidents', {
    method: 'POST',
    headers: authHeader ? { Authorization: authHeader } : {},
    body,
  });
}