import { NextResponse } from 'next/server';

/**
 * External API base URL for candidate records.
 * Points to the 4Geeks Playground Talent Tracker API (public, no auth needed).
 */
const RECORDS_API_BASE = 'https://playground.4geeks.com/tracker/api/v1';

/**
 * Proxy a request to the external 4Geeks Talent Tracker API.
 *
 * This replaces the local TinyDB-based backend with the shared playground API
 * so all users work against the same dataset. No auth headers are forwarded
 * since the playground API is public.
 */
export async function proxyToRecordsBackend(path: string, init?: RequestInit) {
  const url = `${RECORDS_API_BASE}${path}`;

  try {
    const response = await fetch(url, {
      ...init,
      cache: 'no-store',
      headers: {
        'Content-Type': 'application/json',
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
          : payload?.detail || payload?.message || payload?.error || `Error al consumir candidatos`;
      return NextResponse.json({ error: message }, { status: response.status });
    }

    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Error de conexión con la API de candidatos';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}