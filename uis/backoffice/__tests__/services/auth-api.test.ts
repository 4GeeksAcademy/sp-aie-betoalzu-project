import type { LoginResponse } from "@/types/auth";
import { loginApi, registerApi, decodeTokenPayload, forgotPasswordApi, resetPasswordApi, changePasswordApi } from "@/services/auth-api";

// Mock window.location to prevent jsdom navigation errors
const mockLocation = JSON.parse(JSON.stringify(window.location));
beforeAll(() => {
  delete (window as any).location;
  (window as any).location = { href: "" };
});
afterAll(() => {
  (window as any).location = mockLocation;
});

// ======================================================================
// Test: loginApi
// ======================================================================

describe("loginApi", () => {
  const mockToken = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbGljZUBleGFtcGxlLmNvbSIsInJvbGUiOiJ1c2VyIn0.test";

  beforeEach(() => {
    jest.resetAllMocks();
  });

  // F.1.1 — Feliz: Email y contraseña correctos → LoginResponse con access_token
  it("F.1.1 returns LoginResponse on successful login", async () => {
    const mockResponse: LoginResponse = {
      access_token: mockToken,
      token_type: "bearer",
    };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockResponse,
    });

    const result = await loginApi("alice@example.com", "testpass123");
    expect(result).toEqual(mockResponse);
    expect(result.access_token).toBe(mockToken);
    expect(result.token_type).toBe("bearer");

    expect(global.fetch).toHaveBeenCalledWith("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "alice@example.com", password: "testpass123" }),
    });
  });

  // F.1.2 — Fallo: Credenciales inválidas → lanza Error
  it("F.1.2 throws Error on invalid credentials", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Invalid email or password." }),
    });

    await expect(loginApi("alice@example.com", "wrongpass")).rejects.toThrow("Invalid email or password.");
  });

  // F.1.3 — Fallo: Error de red → la promesa se rechaza
  it("F.1.3 rejects on network error", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));

    await expect(loginApi("alice@example.com", "testpass123")).rejects.toThrow("Network error");
  });

  it("handles non-JSON error response", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: new Headers({ "content-type": "text/plain" }),
      text: async () => "Internal Server Error",
    });

    await expect(loginApi("alice@example.com", "testpass123")).rejects.toThrow("Internal Server Error");
  });

  it("handles error response with message field", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ message: "Bad request" }),
    });

    await expect(loginApi("alice@example.com", "testpass123")).rejects.toThrow("Bad request");
  });

  it("handles error response with error field", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ error: "Validation error" }),
    });

    await expect(loginApi("alice@example.com", "testpass123")).rejects.toThrow("Validation error");
  });
});

// ======================================================================
// Test: registerApi
// ======================================================================

describe("registerApi", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  // F.2.1 — Feliz: Payload válido → respuesta exitosa
  it("F.2.1 returns successful response on valid registration", async () => {
    const mockResponse = { id: 1, email: "newuser@example.com", role: "user", is_active: true, created_at: "2026-01-01T00:00:00+00:00" };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockResponse,
    });

    const result = await registerApi({
      email: "newuser@example.com",
      password: "securepass123",
    });

    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "newuser@example.com", password: "securepass123" }),
    });
  });

  // F.2.2 — Fallo: Email duplicado → lanza Error
  it("F.2.2 throws Error on duplicate email", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 409,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ error: "User with email 'existing@example.com' already exists." }),
    });

    await expect(
      registerApi({ email: "existing@example.com", password: "securepass123" })
    ).rejects.toThrow("User with email 'existing@example.com' already exists.");
  });

  // F.2.3 — Fallo: Contraseña muy corta → lanza Error
  it("F.2.3 throws Error on short password", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        detail: "String should have at least 6 characters",
      }),
    });

    await expect(
      registerApi({ email: "test@example.com", password: "12" })
    ).rejects.toThrow("String should have at least 6 characters");
  });

  it("throws error on network failure during registration", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Failed to fetch"));

    await expect(
      registerApi({ email: "test@example.com", password: "securepass123" })
    ).rejects.toThrow("Failed to fetch");
  });
});

// ======================================================================
// Test: decodeTokenPayload
// ======================================================================

describe("decodeTokenPayload", () => {
  // F.3.1 — Feliz: Token JWT válido → devuelve { sub, role }
  it("F.3.1 decodes a valid JWT token", () => {
    // Create a valid JWT with known payload
    const payload = { sub: "alice@example.com", role: "user" };
    const encoded = btoa(JSON.stringify(payload));
    const token = `header.${encoded}.signature`;

    const result = decodeTokenPayload(token);
    expect(result).toEqual(payload);
  });

  it("decodes token with admin role", () => {
    const payload = { sub: "admin@example.com", role: "admin" };
    const encoded = btoa(JSON.stringify(payload));
    const token = `header.${encoded}.signature`;

    const result = decodeTokenPayload(token);
    expect(result).toEqual(payload);
  });

  // F.3.2 — Fallo: Token malformado (sin 3 partes) → devuelve null
  it("F.3.2 returns null for malformed token (no 3 parts)", () => {
    expect(decodeTokenPayload("invalidtoken")).toBeNull();
    expect(decodeTokenPayload("part1.part2")).toBeNull();
    expect(decodeTokenPayload("")).toBeNull();
  });

  // F.3.3 — Fallo: Payload no es JSON válido → devuelve null
  it("F.3.3 returns null when payload is not valid JSON", () => {
    const token = `header.${btoa("not-json")}.signature`;
    expect(decodeTokenPayload(token)).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(decodeTokenPayload("")).toBeNull();
  });

  it("returns null for null or undefined", () => {
    expect(decodeTokenPayload(null as unknown as string)).toBeNull();
    expect(decodeTokenPayload(undefined as unknown as string)).toBeNull();
  });
});

// ======================================================================
// Test: forgotPasswordApi
// ======================================================================

describe("forgotPasswordApi", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  it("sends forgot password request and returns message", async () => {
    const mockResponse = {
      message:
        "Si esa direccion de correo esta registrada, recibiras un enlace para restablecer tu contrasena en breve.",
    };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockResponse,
    });

    const result = await forgotPasswordApi("alice@example.com");
    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "alice@example.com" }),
    });
  });

  it("throws on server error", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Validation error" }),
    });

    await expect(forgotPasswordApi("invalid")).rejects.toThrow("Validation error");
  });
});

// ======================================================================
// Test: resetPasswordApi
// ======================================================================

describe("resetPasswordApi", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  it("sends reset password request and returns message", async () => {
    const mockResponse = { message: "Contrasena restablecida correctamente." };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockResponse,
    });

    const result = await resetPasswordApi("valid-token", "newpass456");
    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: "valid-token", new_password: "newpass456" }),
    });
  });

  it("throws on expired token", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ error: "El token ha expirado." }),
    });

    await expect(resetPasswordApi("expired-token", "newpass456")).rejects.toThrow("El token ha expirado.");
  });
});

// ======================================================================
// Test: changePasswordApi
// ======================================================================

describe("changePasswordApi", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  it("sends change password request and returns message", async () => {
    const mockResponse = { message: "Contrasena actualizada correctamente." };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockResponse,
    });

    const result = await changePasswordApi("currentpass", "newpass456");
    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: "currentpass", new_password: "newpass456" }),
    });
  });

  it("throws on incorrect current password", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ error: "La contrasena actual es incorrecta." }),
    });

    await expect(changePasswordApi("wrongpass", "newpass456")).rejects.toThrow("La contrasena actual es incorrecta.");
  });
});