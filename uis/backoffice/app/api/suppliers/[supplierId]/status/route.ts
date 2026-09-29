import { proxyToSuppliersBackend } from '../../_shared';

type Params = {
  params: Promise<{ supplierId: string }>;
};

export async function PATCH(request: Request, { params }: Params) {
  const { supplierId } = await params;
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToSuppliersBackend(`/suppliers/${supplierId}/status`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}
