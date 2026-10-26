import { proxyToBackend } from '@/lib/backend-proxy';

export async function GET(request: Request) {
  const authHeader = request.headers.get('authorization') || '';

  return proxyToBackend({
    path: '/rfp-intake/tickets',
    init: {
      method: 'GET',
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    label: 'recepción de RFP',
    forwardAuth: true,
  });
}

export async function POST(request: Request) {
  const authHeader = request.headers.get('authorization') || '';
  const body = await request.formData();

  return proxyToBackend({
    path: '/rfp-intake/tickets',
    init: {
      method: 'POST',
      headers: authHeader ? { Authorization: authHeader } : {},
      body,
    },
    label: 'recepción de RFP',
    forwardAuth: true,
  });
}
