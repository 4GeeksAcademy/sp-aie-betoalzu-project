import { proxyToInventoryBackend } from '../_shared';

/**
 * Catch-all API route: /api/inventory/[...slug]
 *
 * Proxies all inventory-related requests to the Python backend.
 * Examples:
 *   /api/inventory/products          → /inventory/products
 *   /api/inventory/products/1        → /inventory/products/1
 *   /api/inventory/orders            → /inventory/orders
 *   /api/inventory/orders/inbound    → /inventory/orders/inbound
 *   /api/inventory/orders/outbound   → /inventory/orders/outbound
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const slug = await params;
  const path = `/inventory/${slug.slug.join('/')}`;
  const authHeader = request.headers.get('authorization') || '';
  return proxyToInventoryBackend(path, {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ slug: string[] }> },
) {
  const slug = await params;
  const path = `/inventory/${slug.slug.join('/')}`;
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToInventoryBackend(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}