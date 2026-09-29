import { NextResponse } from 'next/server';

type ProxyOptions = {
  /** Path to proxy to on the backend */
  path: string;
  /** Original RequestInit to forward */
  init?: RequestInit;
  /** Label for error messages (e.g. 'incidencias', 'inventario') */
  label?: string;
  /** Whether to forward the Authorization header from the request */
  forwardAuth?: boolean;
  /** Allow empty API_URL (falls back to localhost) — false for data APIs, true for auth */
  allowEmptyUrl?: boolean;
};

/**
 * Unified proxy for all backend API calls from Next.js API Routes.
 *
 * Resolves the backend URL using:
 *   1. `API_URL` (preferred)
 *   2. `NEXT_PUBLIC_API_URL` (for data APIs)
 *   3. `BACKEND_URL` (for auth/profiles)
 *   4. `http://localhost:8000` (fallback when `allowEmptyUrl` is true)
 */
function resolveUrl(allowEmptyUrl: boolean): string {
  const url =
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (allowEmptyUrl ? process.env.BACKEND_URL || 'http://localhost:8000' : '') ||
    '';
  return url.replace(/\/$/, '');
}

/**
 * Proxy a request to the Python backend.
 * Runs server-side, so internal URLs are always reachable.
 */
export async function proxyToBackend(options: ProxyOptions): Promise<NextResponse> {
  const { path, init, label = 'servicio', forwardAuth = false, allowEmptyUrl = false } = options;
  const backendUrl = resolveUrl(allowEmptyUrl);

  if (!backendUrl) {
    return NextResponse.json(
      { error: `No se configuró API_URL, NEXT_PUBLIC_API_URL ni BACKEND_URL para ${label}.` },
      { status: 500 },
    );
  }

  // Extract Authorization header from the incoming request if forwarding is enabled
  const authHeader =
    forwardAuth && init?.headers && 'Authorization' in (init.headers as Record<string, string>)
      ? (init.headers as Record<string, string>).Authorization
      : undefined;

  try {
    const response = await fetch(`${backendUrl}${path}`, {
      ...init,
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { Authorization: authHeader } : {}),
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
          : payload?.detail || payload?.message || payload?.error || `Error al consumir ${label}`;
      return NextResponse.json({ error: message }, { status: response.status });
    }

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : `Fallo de conexion con ${label}`;
    return NextResponse.json({ error: message }, { status: 502 });
  }
}