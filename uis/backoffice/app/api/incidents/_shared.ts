import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Proxy a request to the incidents API backend.
 * Forwards the Authorization header if present.
 */
export async function proxyToIncidentBackend(
  path: string,
  init?: RequestInit & { duplex?: 'half' },
  passthrough = false,
) {
  return proxyToBackend({
    path,
    init,
    label: 'incidencias',
    forwardAuth: true,
    passthrough,
  });
}