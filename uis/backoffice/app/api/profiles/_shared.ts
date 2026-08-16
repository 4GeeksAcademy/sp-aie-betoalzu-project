import { NextResponse } from 'next/server';

function resolveBackendUrl() {
  return (process.env.API_URL || process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '');
}

/**
 * Proxy a profiles request to the Python backend.
 * Runs server-side, so `localhost:8000` is always reachable.
 */
export async function proxyProfileRequest(
  path: string,
  init?: RequestInit,
): Promise<NextResponse> {
  const backendUrl = resolveBackendUrl();

  try {
    const response = await fetch(`${backendUrl}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers || {}),
      },
    });

    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const message =
        typeof payload === 'string'
          ? payload
          : payload?.detail || payload?.message || payload?.error || 'Error del servidor';
      return NextResponse.json({ error: message }, { status: response.status });
    }

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : 'Error de conexion con el backend';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
