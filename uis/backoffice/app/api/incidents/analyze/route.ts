import { NextResponse } from 'next/server';
import { analyzeCsvText, buildSummary, CsvAnalysisError, setLastAnalysis } from '@/lib/incidents-analyzer';

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const upload = form.get('file');

    if (!(upload instanceof File)) {
      return NextResponse.json({ error: "Debe enviarse un fichero CSV en el campo 'file'." }, { status: 400 });
    }

    if (!upload.name) {
      return NextResponse.json({ error: 'Debe seleccionarse un fichero CSV.' }, { status: 400 });
    }

    if (!upload.name.toLowerCase().endsWith('.csv')) {
      return NextResponse.json({ error: 'El fichero debe tener extension .csv.' }, { status: 415 });
    }

    const text = await upload.text();
    const result = analyzeCsvText(text, upload.name);
    setLastAnalysis(result);

    return NextResponse.json(buildSummary(result));
  } catch (error) {
    if (error instanceof CsvAnalysisError) {
      return NextResponse.json({ error: error.message }, { status: error.statusCode });
    }

    return NextResponse.json({ error: 'No fue posible analizar el fichero CSV.' }, { status: 500 });
  }
}