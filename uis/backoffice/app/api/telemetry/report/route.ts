import { proxyToBackend } from '../../../../lib/backend-proxy';

export async function GET() {
  return proxyToBackend({
    path: '/telemetry/report',
    label: 'telemetría',
  });
}
