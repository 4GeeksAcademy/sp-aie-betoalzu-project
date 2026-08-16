import { proxyProfileRequest } from '../_shared';

/**
 * GET /api/profiles/me
 * Proxies to GET /profiles/me on the Python backend (protected).
 * Returns the authenticated user's profile.
 */
export async function GET(request: Request) {
  const authHeader = request.headers.get('authorization') || undefined;

  return proxyProfileRequest('/profiles/me', {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

/**
 * PUT /api/profiles/me
 * Proxies to PUT /profiles/me on the Python backend (protected).
 * Updates name, phone and address for the authenticated user.
 */
export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const authHeader = request.headers.get('authorization') || undefined;

    return proxyProfileRequest('/profiles/me', {
      method: 'PUT',
      body: JSON.stringify(body),
      headers: authHeader ? { Authorization: authHeader } : {},
    });
  } catch {
    return new Response(
      JSON.stringify({ error: 'Cuerpo de peticion invalido.' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } },
    );
  }
}
