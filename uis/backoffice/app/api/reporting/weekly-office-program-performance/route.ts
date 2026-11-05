import { proxyToBackend } from '../../../../lib/backend-proxy';

export async function GET(request: Request) {
  const authHeader = request.headers.get('authorization') || '';
  const weekStart = new URL(request.url).searchParams.get('week_start');
  const query = new URLSearchParams();
  if (weekStart !== null) query.set('week_start', weekStart);
  const search = query.size ? `?${query}` : '';

  return proxyToBackend({
    path: `/reporting/weekly-office-program-performance${search}`,
    init: {
      method: 'GET',
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    label: 'reporte semanal',
    forwardAuth: true,
  });
}
