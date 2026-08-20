import { NextResponse } from 'next/server';
import { proxyToIncidentBackend } from '../_shared';

function getAuthFromRequest(request: Request): Record<string, string> {
  const auth = request.headers.get('authorization') || '';
  return auth ? { Authorization: auth } : {};
}

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToIncidentBackend(`/api/incidents/${id}`, { method: 'GET', headers: getAuthFromRequest(request) });
}

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = await request.text();
  return proxyToIncidentBackend(`/api/incidents/${id}`, {
    method: 'PUT',
    headers: getAuthFromRequest(request),
    body,
  });
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyToIncidentBackend(`/api/incidents/${id}`, { method: 'DELETE', headers: getAuthFromRequest(request) });
}