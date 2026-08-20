import { proxyToBackend } from '../_shared';

type Params = {
  params: Promise<{ supplierId: string }>;
};

export async function GET(_: Request, { params }: Params) {
  const { supplierId } = await params;
  return proxyToBackend(`/suppliers/${supplierId}`, { method: 'GET' });
}

export async function PUT(request: Request, { params }: Params) {
  const { supplierId } = await params;
  const body = await request.text();
  return proxyToBackend(`/suppliers/${supplierId}`, {
    method: 'PUT',
    body,
  });
}

export async function DELETE(_: Request, { params }: Params) {
  const { supplierId } = await params;
  return proxyToBackend(`/suppliers/${supplierId}`, { method: 'DELETE' });
}
