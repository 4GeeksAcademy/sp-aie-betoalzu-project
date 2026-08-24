import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Proxy a profiles request to the Python backend.
 * Uses BACKEND_URL with fallback to localhost:8000.
 */
export async function proxyProfileRequest(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return proxyToBackend({
    path,
    init,
    label: 'perfiles',
    allowEmptyUrl: true,
  });
}
