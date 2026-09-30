import { proxyToIncidentBackend } from '../_shared';

export async function POST(request: Request) {
  const authorization = request.headers.get('authorization');
  const contentType = request.headers.get('content-type');
  return proxyToIncidentBackend(
    '/api/incidents/analyze',
    {
      method: 'POST',
      body: request.body,
      duplex: 'half',
      headers: {
        ...(authorization ? { Authorization: authorization } : {}),
        ...(contentType ? { 'Content-Type': contentType } : {}),
      },
    },
  );
}