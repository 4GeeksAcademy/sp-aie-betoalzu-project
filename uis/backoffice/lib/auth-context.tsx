'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { AuthContextType, AuthUser, RegisterPayload } from '../types/auth';
import {
  getStoredToken,
  setStoredToken,
  removeStoredToken,
} from '../lib/auth-token';
import {
  loginApi,
  registerApi,
  decodeTokenPayload,
  getCurrentUserApi,
} from '../services/auth-api';

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: check if there is a stored token and try to restore user info
  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }

    setToken(stored);
    const payload = decodeTokenPayload(stored);

    if (!payload) {
      removeStoredToken();
      setToken(null);
      setLoading(false);
      return;
    }

    // Build a minimal user from JWT claims while we fetch the full profile
    const minimalUser: AuthUser = {
      id: 0,
      email: payload.sub,
      role: payload.role,
      is_active: true,
      created_at: '',
    };
    setUser(minimalUser);

    // Try to fetch the full user profile using the email as identifier.
    // The backend uses numeric IDs, so we first need to look up the user.
    // For now, we rely on the JWT payload and a lightweight fetch.
    // If the token is expired the server will return 401 and we clean up.
    getCurrentUserApi(0)
      .then((fullUser) => {
        setUser(fullUser);
      })
      .catch(() => {
        // Token expired or invalid — clean up
        removeStoredToken();
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await loginApi(email, password);
    setStoredToken(res.access_token);
    setToken(res.access_token);

    const payload = decodeTokenPayload(res.access_token);
    if (payload) {
      setUser({
        id: 0,
        email: payload.sub,
        role: payload.role,
        is_active: true,
        created_at: '',
      });
    }
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    // 1. Register the user
    await registerApi(payload);

    // 2. Auto-login with the same credentials
    const loginRes = await loginApi(payload.email, payload.password);
    setStoredToken(loginRes.access_token);
    setToken(loginRes.access_token);

    const decoded = decodeTokenPayload(loginRes.access_token);
    if (decoded) {
      setUser({
        id: 0,
        email: decoded.sub,
        role: decoded.role,
        is_active: true,
        created_at: '',
      });
    }
  }, []);

  const logout = useCallback(() => {
    removeStoredToken();
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  }, []);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      token,
      loading,
      login,
      register,
      logout,
      isAuthenticated: !!token,
    }),
    [user, token, loading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth debe usarse dentro de un <AuthProvider>');
  }
  return ctx;
}
