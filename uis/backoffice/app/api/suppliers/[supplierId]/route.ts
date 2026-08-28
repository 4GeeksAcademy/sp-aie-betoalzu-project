import { proxyToSuppliersBackend } from '../_shared';

type Params = {
  params: Promise<{ supplierId: string }>;
};

export async function GET(request: Request, { params }: Params) {
  const { supplierId } = await params;
  const authHeader = request.headers.get('authorization') || '';
  return proxyToSuppliersBackend(`/suppliers/${supplierId}`, {
    method: 'GET',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}

export async function PUT(request: Request, { params }: Params) {
  const { supplierId } = await params;
  const body = await request.text();
  const authHeader = request.headers.get('authorization') || '';
  return proxyToSuppliersBackend(`/suppliers/${supplierId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(authHeader ? { Authorization: authHeader } : {}),
    },
    body,
  });
}

export async function DELETE(request: Request, { params }: Params) {
  const { supplierId } = await params;
  const authHeader = request.headers.get('authorization') || '';
  return proxyToSuppliersBackend(`/suppliers/${supplierId}`, {
    method: 'DELETE',
    headers: authHeader ? { Authorization: authHeader } : {},
  });
}
