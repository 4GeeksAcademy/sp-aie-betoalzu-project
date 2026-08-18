import {
  getStoredToken,
  setStoredToken,
  removeStoredToken,
  getAuthHeaders,
  getTokenFromCookie,
} from "@/lib/auth-token";

// ======================================================================
// Test: Token storage utils (auth-token.ts)
// ======================================================================

describe("token storage utils", () => {
  const TOKEN_KEY = "nexova_token";
  const COOKIE_NAME = "nexova_token";
  const testToken = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZUBleGFtcGxlLmNvbSIsInJvbGUiOiJ1c2VyIn0.test";

  beforeEach(() => {
    // Clear localStorage and cookies before each test
    localStorage.clear();
    document.cookie = `${COOKIE_NAME}=; Path=/; SameSite=Lax; Max-Age=0`;
  });

  // F.4.1 — Feliz: setStoredToken → persiste en localStorage y cookie
  describe("setStoredToken", () => {
    it("F.4.1 stores token in localStorage and cookie", () => {
      setStoredToken(testToken);

      expect(localStorage.getItem(TOKEN_KEY)).toBe(testToken);
      expect(document.cookie).toContain(encodeURIComponent(testToken));
    });
  });

  // F.4.2 — Feliz: getStoredToken → recupera el token guardado
  describe("getStoredToken", () => {
    it("F.4.2 retrieves stored token from localStorage", () => {
      localStorage.setItem(TOKEN_KEY, testToken);
      expect(getStoredToken()).toBe(testToken);
    });
  });

  // F.4.4 — Límite: getStoredToken sin token previo → devuelve null
  describe("getStoredToken - no token", () => {
    it("F.4.4 returns null when no token is stored", () => {
      localStorage.clear();
      expect(getStoredToken()).toBeNull();
    });
  });

  // F.4.3 — Feliz: removeStoredToken → elimina token de localStorage y cookie
  describe("removeStoredToken", () => {
    it("F.4.3 removes token from localStorage and cookie", () => {
      localStorage.setItem(TOKEN_KEY, testToken);
      removeStoredToken();

      expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
      // Cookie should be removed (Max-Age=0 means immediate expiry)
      expect(document.cookie).not.toContain(COOKIE_NAME);
    });
  });

  // F.4.5 — Feliz: getAuthHeaders con token → { Authorization: "Bearer <token>" }
  describe("getAuthHeaders", () => {
    it("F.4.5 returns Authorization header with Bearer token", () => {
      localStorage.setItem(TOKEN_KEY, testToken);
      const headers = getAuthHeaders();
      expect(headers).toEqual({ Authorization: `Bearer ${testToken}` });
    });
  });

  // F.4.6 — Límite: getAuthHeaders sin token → {}
  describe("getAuthHeaders - no token", () => {
    it("F.4.6 returns empty object when no token is stored", () => {
      localStorage.clear();
      expect(getAuthHeaders()).toEqual({});
    });
  });

  // F.4.7 — Feliz: getTokenFromCookie con cookie presente → devuelve el token
  describe("getTokenFromCookie", () => {
    it("F.4.7 retrieves token from cookie header string", () => {
      const cookieHeader = `${COOKIE_NAME}=${encodeURIComponent(testToken)}; other=value`;
      const result = getTokenFromCookie(cookieHeader);
      expect(result).toBe(testToken);
    });

    it("retrieves token from cookie with multiple cookies", () => {
      const cookieHeader = `session=abc; ${COOKIE_NAME}=${encodeURIComponent(testToken)}; theme=dark`;
      const result = getTokenFromCookie(cookieHeader);
      expect(result).toBe(testToken);
    });
  });

  // F.4.8 — Límite: getTokenFromCookie sin cookie → devuelve null
  describe("getTokenFromCookie - no cookie", () => {
    it("F.4.8 returns null when cookie header is null", () => {
      expect(getTokenFromCookie(null)).toBeNull();
    });

    it("returns null when cookie header is empty", () => {
      expect(getTokenFromCookie("")).toBeNull();
    });

    it("returns null when cookie does not contain the token", () => {
      const cookieHeader = "other=value; session=abc";
      expect(getTokenFromCookie(cookieHeader)).toBeNull();
    });
  });
});