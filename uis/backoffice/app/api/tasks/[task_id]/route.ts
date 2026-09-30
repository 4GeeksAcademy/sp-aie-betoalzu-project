import { proxyToIncidentBackend } from '../../incidents/_shared';

export async function GET(request: Request, { params }: { params: Promise<{ task_id: string }> }) {
  const { task_id: taskId } = await params;
  const authorization = request.headers.get('authorization');
  return proxyToIncidentBackend(`/tasks/${encodeURIComponent(taskId)}`, {
    method: 'GET',
    headers: authorization ? { Authorization: authorization } : {},
  });
}