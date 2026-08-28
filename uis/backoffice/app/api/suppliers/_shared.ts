import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Proxy a request to the suppliers API backend.
 * Forwards the Authorization header if present.
 */
export async function proxyToSuppliersBackend(path: string, init?: RequestInit) {
  return proxyToBackend({
    path,
    init,
    label: 'proveedores',
    forwardAuth: true,
  });
}
