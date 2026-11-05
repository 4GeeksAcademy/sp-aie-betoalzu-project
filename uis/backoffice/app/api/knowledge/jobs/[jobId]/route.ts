import { proxyToBackend } from '../../../../../lib/backend-proxy';

export async function GET(
  request: Request,
  context: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await context.params;
  const authHeader = request.headers.get('authorization') || '';
  return proxyToBackend({
    path: `/knowledge/jobs/${encodeURIComponent(jobId)}`,
    init: {
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    label: 'base de conocimiento',
    forwardAuth: true,
  });
}
