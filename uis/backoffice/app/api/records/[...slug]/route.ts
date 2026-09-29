import { proxyToRecordsBackend } from '../_shared';

/**
 * Catch-all API route: /api/records/[...slug]
 *
 * Proxies all records-related requests to the external 4Geeks API.
 * Examples:
 *   /api/records/123                 → /records/123
 *   /api/records/123/notes           → /records/123/notes
 *   /api/records?page=1&limit=20    → /records?page=1&limit=20
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const slug = await params;
  const { searchParams } = new URL(request.url);
  const queryString = searchParams.toString();
  const path = queryString
    ? `/records/${slug.slug.join('/')}?${queryString}`
    : `/records/${slug.slug.join('/')}`;
  const authHeader = request.headers.get('authorization') || '';
  return proxyToRecordsBackend(path, {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const slug = await params;
  const path = `/records/${slug.slug.join('/')}`;
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToRecordsBackend(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const slug = await params;
  const path = `/records/${slug.slug.join('/')}`;
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToRecordsBackend(path, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const slug = await params;
  const path = `/records/${slug.slug.join('/')}`;
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToRecordsBackend(path, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const slug = await params;
  const path = `/records/${slug.slug.join('/')}`;
  const authHeader = request.headers.get('authorization') || '';
  return proxyToRecordsBackend(path, {
    method: 'DELETE',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}