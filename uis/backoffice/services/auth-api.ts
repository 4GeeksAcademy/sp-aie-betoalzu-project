import type {
  LoginResponse,
  RegisterPayload,
  AuthUser,
  ProfileData,
} from '../types/auth';
import { getAuthHeaders, removeStoredToken } from '../lib/auth-token';

/**
 * Handle API response and throw on errors.
 * If a 401 is received, clears the stored token and redirects to /login.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    // 401 Unauthorized — token expired or invalid
    if (res.status === 401) {
      removeStoredToken();
      // Redirect to login (use window.location for full page reload to clear state)
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }

    const message =
      typeof payload === 'string'
        ? payload
        : payload?.detail || payload?.message || payload?.error || 'Error en la petición';
    throw new Error(message);
  }

  return payload as T;
}

/**
 * POST /api/auth/login — proxies to backend POST /login.
 * Uses same-origin Next.js API route so it works in Codespaces and production.
 */
export async function loginApi(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<LoginResponse>(res);
}

/**
 * POST /api/auth/register — proxies to backend POST /users.
 */
export async function registerApi(payload: RegisterPayload): Promise<unknown> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse<unknown>(res);
}

/**
 * GET /api/auth/me?id=N — proxies to backend GET /users/{id} (protected).
 */
export async function getCurrentUserApi(userId: number): Promise<AuthUser> {
  const res = await fetch(`/api/auth/me?id=${userId}`, {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
    },
  });
  return handleResponse<AuthUser>(res);
}

/**
 * Decode JWT payload to extract user info (id, email, role) without
 * calling an extra endpoint.  This is a lightweight helper; the token
 * is still validated server-side on every protected request.
 */
export function decodeTokenPayload(token: string): { sub: string; role: string } | null {
  try {
    const base64 = token.split('.')[1];
    const json = atob(base64);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/**
 * PUT /users/{id} — update user credential fields (protected).
 */
export async function updateUserApi(
  userId: number,
  data: { email?: string; password?: string }
): Promise<AuthUser> {
  const res = await fetch(`/api/auth/me?id=${userId}`, {
    method: 'PUT',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return handleResponse<AuthUser>(res);
}

// ---------------------------------------------------------------------------
// Profile endpoints — proxy to /profiles/me
// ---------------------------------------------------------------------------

/**
 * GET /api/profiles/me — get the authenticated user's profile (name, phone, address).
 */
export async function getMyProfileApi(): Promise<ProfileData> {
  const res = await fetch('/api/profiles/me', {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
    },
  });
  return handleResponse<ProfileData>(res);
}

/**
 * PUT /api/profiles/me — update the authenticated user's profile.
 */
export async function updateMyProfileApi(data: {
  name?: string;
  phone?: string;
  address?: string;
}): Promise<ProfileData> {
  const res = await fetch('/api/profiles/me', {
    method: 'PUT',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  return handleResponse<ProfileData>(res);
}
