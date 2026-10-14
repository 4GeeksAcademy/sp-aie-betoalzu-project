import { proxyToBackend } from '../../../../lib/backend-proxy';

export async function POST(request: Request) {
  const authHeader = request.headers.get('authorization') || '';

  return proxyToBackend({
    path: '/knowledge/query',
    init: {
      method: 'POST',
      headers: authHeader ? { Authorization: authHeader } : {},
      body: await request.text(),
    },
    label: 'base de conocimiento',
    forwardAuth: true,
  });
}