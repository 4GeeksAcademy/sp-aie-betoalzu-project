import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Proxy an auth request to the Python backend.
 * Uses BACKEND_URL with fallback to localhost:8000.
 */
export async function proxyAuthRequest(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return proxyToBackend({
    path,
    init,
    label: 'autenticacion',
    allowEmptyUrl: true,
  });
}
