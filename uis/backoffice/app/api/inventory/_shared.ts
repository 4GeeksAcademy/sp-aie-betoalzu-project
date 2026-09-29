import { proxyToBackend } from '@/lib/backend-proxy';

/**
 * Proxy a request to the inventory API backend.
 * Forwards the Authorization header if present.
 */
export async function proxyToInventoryBackend(path: string, init?: RequestInit) {
  return proxyToBackend({
    path,
    init,
    label: 'inventario',
    forwardAuth: true,
  });
}