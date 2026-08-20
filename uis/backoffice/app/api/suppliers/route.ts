import { proxyToBackend } from './_shared';

export async function GET() {
  return proxyToBackend('/suppliers', { method: 'GET' });
}

export async function POST(request: Request) {
  const body = await request.text();
  return proxyToBackend('/suppliers', {
    method: 'POST',
    body,
  });
}
