import { proxyToSuppliersBackend } from './_shared';

export async function GET(request: Request) {
  const authHeader = request.headers.get('authorization') || '';
  return proxyToSuppliersBackend('/suppliers', {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

export async function POST(request: Request) {
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToSuppliersBackend('/suppliers', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}
