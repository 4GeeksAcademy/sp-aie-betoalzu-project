import { proxyToRecordsBackend } from './_shared';

/**
 * API route: /api/records
 *
 * Proxies base records requests (list / create) to the external 4Geeks API.
 * Forwards query parameters (page, limit, search, etc.) correctly.
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const queryString = searchParams.toString();
  const path = queryString ? `/records?${queryString}` : '/records';
  const authHeader = request.headers.get('authorization') || '';
  return proxyToRecordsBackend(path, {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

export async function POST(request: Request) {
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToRecordsBackend('/records', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}