const TOKEN_KEY = 'nexova_token';
const COOKIE_NAME = 'nexova_token';
const COOKIE_MAX_AGE = 60 * 60; // 1 hour in seconds

function setCookie(name: string, value: string, maxAge: number) {
  if (typeof document === 'undefined') return;
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; SameSite=Lax; Max-Age=${maxAge}`;
}

function removeCookie(name: string) {
  if (typeof document === 'undefined') return;
  document.cookie = `${name}=; Path=/; SameSite=Lax; Max-Age=0`;
}

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** Read token from cookie (used by middleware). */
export function getTokenFromCookie(cookieHeader: string | null): string | null {
  if (!cookieHeader) return null;
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${COOKIE_NAME}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  setCookie(COOKIE_NAME, token, COOKIE_MAX_AGE);
}

export function removeStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  removeCookie(COOKIE_NAME);
}

export function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
