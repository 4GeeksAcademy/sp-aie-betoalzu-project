import { NextResponse } from 'next/server';
import { buildMetricsCsv, getLastAnalysis } from '@/lib/incidents-analyzer';

export async function GET() {
  const lastAnalysis = getLastAnalysis();
  if (!lastAnalysis) {
    return NextResponse.json({ error: 'No hay analisis previo para exportar.' }, { status: 404 });
  }

  const fileName = `${lastAnalysis.source_file.replace(/\.csv$/i, '')}-metrics.csv`;
  const csv = buildMetricsCsv(lastAnalysis);

  return new Response(csv, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${fileName}"`,
    },
  });
}