import { NextResponse } from 'next/server';

function resolveApiUrl() {
  return (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
}

export async function proxyToInventoryBackend(path: string, init?: RequestInit) {
  const apiUrl = resolveApiUrl();

  if (!apiUrl) {
    return NextResponse.json(
      { error: 'No se configuró API_URL o NEXT_PUBLIC_API_URL para inventario.' },
      { status: 500 },
    );
  }

  const authHeader =
    init?.headers && 'Authorization' in (init.headers as Record<string, string>)
      ? (init.headers as Record<string, string>).Authorization
      : undefined;

  try {
    const response = await fetch(`${apiUrl}${path}`, {
      ...init,
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { Authorization: authHeader } : {}),
        ...(init?.headers || {}),
      },
    });

    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const message =
        typeof payload === 'string'
          ? payload
          : payload?.detail || payload?.message || payload?.error || 'Error al consumir inventario';
      return NextResponse.json({ error: message }, { status: response.status });
    }

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Fallo de conexión con API de inventario';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}