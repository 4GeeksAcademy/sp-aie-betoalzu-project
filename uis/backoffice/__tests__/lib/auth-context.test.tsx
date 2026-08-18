import React from "react";
import { render, screen, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/lib/auth-context";

// ======================================================================
// Test: AuthProvider login, register, logout flows
// ======================================================================

// Mock the auth-api module
jest.mock("@/services/auth-api", () => ({
  loginApi: jest.fn(),
  registerApi: jest.fn(),
  decodeTokenPayload: jest.fn(),
  getMyProfileApi: jest.fn(),
}));

// Mock the auth-token module
jest.mock("@/lib/auth-token", () => ({
  getStoredToken: jest.fn(),
  setStoredToken: jest.fn(),
  removeStoredToken: jest.fn(),
}));

import {
  loginApi,
  registerApi,
  decodeTokenPayload,
  getMyProfileApi,
} from "@/services/auth-api";
import {
  getStoredToken,
  setStoredToken,
  removeStoredToken,
} from "@/lib/auth-token";

// Helper to get text content from test elements
function getText(id: string): string {
  return screen.getByTestId(id).textContent || "";
}

// Helper component that uses the auth context
function TestConsumer() {
  const { user, token, loading, isAuthenticated, login, register, logout } =
    useAuth();

  return (
    <div>
      <div data-testid="loading">{loading.toString()}</div>
      <div data-testid="isAuthenticated">{isAuthenticated.toString()}</div>
      <div data-testid="token">{token ?? "null"}</div>
      <div data-testid="user-email">{user?.email ?? "null"}</div>
      <div data-testid="user-role">{user?.role ?? "null"}</div>
      <button
        data-testid="login-btn"
        onClick={() => login("test@example.com", "password123")}
      >
        Login
      </button>
      <button
        data-testid="register-btn"
        onClick={() =>
          register({ email: "new@example.com", password: "newpass123" })
        }
      >
        Register
      </button>
      <button data-testid="logout-btn" onClick={logout}>
        Logout
      </button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>
  );
}

describe("AuthProvider", () => {
  const mockToken =
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwicm9sZSI6InVzZXIifQ.test";
  const mockPayload = { sub: "test@example.com", role: "user" };

  beforeEach(() => {
    jest.clearAllMocks();
    (getStoredToken as jest.Mock).mockReturnValue(null);
    (decodeTokenPayload as jest.Mock).mockReturnValue(null);
    (loginApi as jest.Mock).mockResolvedValue({
      access_token: mockToken,
      token_type: "bearer",
    });
    (registerApi as jest.Mock).mockResolvedValue({ id: 1, email: "new@example.com" });
    (getMyProfileApi as jest.Mock).mockResolvedValue({
      id: 1,
      user_id: 1,
      name: "Test User",
      phone: null,
      address: null,
    });
  });

  // Initial state: no token stored
  it("starts with no user when no token is stored", async () => {
    renderWithProvider();

    await waitFor(() => {
      expect(getText("loading")).toBe("false");
    });

    expect(getText("isAuthenticated")).toBe("false");
    expect(getText("token")).toBe("null");
    expect(getText("user-email")).toBe("null");
  });

  // Login flow: login → save token → load profile
  describe("login", () => {
    it("saves token and sets user on successful login", async () => {
      (decodeTokenPayload as jest.Mock).mockReturnValue(mockPayload);
      renderWithProvider();

      await waitFor(() => {
        expect(getText("loading")).toBe("false");
      });

      // Click login button
      await act(async () => {
        screen.getByTestId("login-btn").click();
      });

      expect(loginApi).toHaveBeenCalledWith("test@example.com", "password123");
      expect(setStoredToken).toHaveBeenCalledWith(mockToken);
      expect(getText("isAuthenticated")).toBe("true");
      expect(getText("user-email")).toBe("test@example.com");
    });

    it("fetches profile after login", async () => {
      (decodeTokenPayload as jest.Mock).mockReturnValue(mockPayload);
      renderWithProvider();

      await waitFor(() => {
        expect(getText("loading")).toBe("false");
      });

      await act(async () => {
        screen.getByTestId("login-btn").click();
      });

      expect(getMyProfileApi).toHaveBeenCalled();
    });
  });

  // Register flow: register → auto-login
  describe("register", () => {
    it("registers and then auto-logins", async () => {
      (decodeTokenPayload as jest.Mock).mockReturnValue(mockPayload);
      renderWithProvider();

      await waitFor(() => {
        expect(getText("loading")).toBe("false");
      });

      await act(async () => {
        screen.getByTestId("register-btn").click();
      });

      expect(registerApi).toHaveBeenCalledWith({
        email: "new@example.com",
        password: "newpass123",
      });
      expect(loginApi).toHaveBeenCalledWith("new@example.com", "newpass123");
      expect(setStoredToken).toHaveBeenCalledWith(mockToken);
      expect(getText("isAuthenticated")).toBe("true");
    });
  });

  // Logout flow: clears token and user
  describe("logout", () => {
    it("clears token and user on logout", async () => {
      (decodeTokenPayload as jest.Mock).mockReturnValue(mockPayload);
      renderWithProvider();

      await waitFor(() => {
        expect(getText("loading")).toBe("false");
      });

      // Login first
      await act(async () => {
        screen.getByTestId("login-btn").click();
      });

      // Then logout
      await act(async () => {
        screen.getByTestId("logout-btn").click();
      });

      expect(removeStoredToken).toHaveBeenCalled();
      expect(getText("isAuthenticated")).toBe("false");
      expect(getText("user-email")).toBe("null");
    });
  });

  // Restore session from stored token on mount
  describe("restore session on mount", () => {
    it("restores user from stored token on mount", async () => {
      (getStoredToken as jest.Mock).mockReturnValue(mockToken);
      (decodeTokenPayload as jest.Mock).mockReturnValue(mockPayload);

      renderWithProvider();

      await waitFor(() => {
        expect(getText("loading")).toBe("false");
      });

      expect(getText("isAuthenticated")).toBe("true");
      expect(getText("user-email")).toBe("test@example.com");
    });

    it("clears invalid stored token on mount", async () => {
      (getStoredToken as jest.Mock).mockReturnValue("invalid-token");
      (decodeTokenPayload as jest.Mock).mockReturnValue(null);

      renderWithProvider();

      await waitFor(() => {
        expect(getText("loading")).toBe("false");
      });

      expect(removeStoredToken).toHaveBeenCalled();
      expect(getText("isAuthenticated")).toBe("false");
    });
  });
});

// Test that useAuth throws outside provider
describe("useAuth outside provider", () => {
  it("throws error when used outside AuthProvider", () => {
    // Suppress console.error for this expected error
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<TestConsumer />)).toThrow(
      "useAuth debe usarse dentro de un <AuthProvider>"
    );

    consoleSpy.mockRestore();
  });
});