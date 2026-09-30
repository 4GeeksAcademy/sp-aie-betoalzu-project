import { NextResponse } from 'next/server';
import { proxyToIncidentBackend } from '../../_shared';

export async function GET(request: Request) {
  const taskId = new URL(request.url).searchParams.get('task_id');
  if (!taskId) {
    return NextResponse.json({ error: 'Debe indicarse task_id.' }, { status: 400 });
  }

  const authorization = request.headers.get('authorization');
  return proxyToIncidentBackend(
    `/api/incidents/results/export?task_id=${encodeURIComponent(taskId)}`,
    {
      method: 'GET',
      headers: authorization ? { Authorization: authorization } : {},
    },
    true,
  );
}