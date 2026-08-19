import { getAuthHeaders } from './auth-token';
import type {
  Product,
  InboundOrderPayload,
  InboundOrderResponse,
  OutboundOrderPayload,
  OutboundOrderResponse,
  Order,
} from '@/types/inventory';

/**
 * Error personalizado para llamadas a la API de inventario.
 */
export class InventoryApiError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.name = 'InventoryApiError';
    this.statusCode = statusCode;
  }
}

/**
 * Procesa la respuesta HTTP y lanza un InventoryApiError si no es exitosa.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    const message =
      typeof payload === 'string'
        ? payload
        : payload?.detail || payload?.message || payload?.error || 'Error en la petición de inventario';
    throw new InventoryApiError(message, res.status);
  }

  return payload as T;
}

// ---------------------------------------------------------------------------
// Products
// ---------------------------------------------------------------------------

/** GET /api/inventory/products — Lista todos los productos con su stock actual */
export async function fetchProducts(): Promise<Product[]> {
  const res = await fetch('/api/inventory/products', {
    method: 'GET',
    headers: { ...getAuthHeaders() },
  });
  return handleResponse<Product[]>(res);
}

/** GET /api/inventory/products/{productId} — Obtiene un producto por ID */
export async function fetchProduct(productId: number): Promise<Product> {
  const res = await fetch(`/api/inventory/products/${productId}`, {
    method: 'GET',
    headers: { ...getAuthHeaders() },
  });
  return handleResponse<Product>(res);
}

// ---------------------------------------------------------------------------
// Orders (Inbound / Outbound)
// ---------------------------------------------------------------------------

/** POST /api/inventory/orders/inbound — Registra una entrada de activos */
export async function createInboundOrder(payload: InboundOrderPayload): Promise<InboundOrderResponse> {
  const res = await fetch('/api/inventory/orders/inbound', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<InboundOrderResponse>(res);
}

/** POST /api/inventory/orders/outbound — Registra una salida de activos */
export async function createOutboundOrder(payload: OutboundOrderPayload): Promise<OutboundOrderResponse> {
  const res = await fetch('/api/inventory/orders/outbound', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<OutboundOrderResponse>(res);
}

/** GET /api/inventory/orders — Lista todas las entradas y salidas */
export async function fetchOrders(): Promise<Order[]> {
  const res = await fetch('/api/inventory/orders', {
    method: 'GET',
    headers: { ...getAuthHeaders() },
  });
  return handleResponse<Order[]>(res);
}