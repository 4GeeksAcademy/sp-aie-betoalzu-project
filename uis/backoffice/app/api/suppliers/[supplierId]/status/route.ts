import { proxyToBackend } from '../../_shared';

type Params = {
  params: Promise<{ supplierId: string }>;
};

export async function PATCH(request: Request, { params }: Params) {
  const { supplierId } = await params;
  const body = await request.text();
  return proxyToBackend(`/suppliers/${supplierId}/status`, {
    method: 'PATCH',
    body,
  });
}
