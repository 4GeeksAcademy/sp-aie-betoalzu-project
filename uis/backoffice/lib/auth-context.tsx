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
  getMyProfileApi,
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

    // Fetch the user's profile from /profiles/me (uses the JWT to identify the user)
    // If the token is expired the server will return 401 and we clean up.
    getMyProfileApi()
      .then((profile) => {
        // Merge profile data into the user object
        setUser((prev) => ({
          ...(prev || minimalUser),
          profile: {
            name: profile.name,
            phone: profile.phone,
            address: profile.address,
          },
        }));
      })
      .catch(() => {
        // Token expired or invalid — clean up and redirect to login
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

      // Fetch profile data after login
      try {
        const profile = await getMyProfileApi();
        setUser((prev) => ({
          ...(prev || { id: 0, email: payload.sub, role: payload.role, is_active: true, created_at: '' }),
          profile: {
            name: profile.name,
            phone: profile.phone,
            address: profile.address,
          },
        }));
      } catch {
        // Profile fetch failed, but login succeeded — user can still use the app
      }
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
