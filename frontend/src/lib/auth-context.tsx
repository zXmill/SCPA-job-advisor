'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api, UserData, ApiError } from './api';

interface AuthState {
  user: UserData | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    try {
      const token = api.getToken();
      if (!token) { setUser(null); setLoading(false); return; }
      const data = await api.getMe();
      setUser(data);
    } catch {
      api.logout();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      refreshUser();
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    setError(null);
    try {
      const { user: u } = await api.login(email, password);
      setUser(u);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Login gagal';
      setError(msg);
      throw e;
    }
  };

  const register = async (name: string, email: string, password: string) => {
    setError(null);
    try {
      const { user: u } = await api.register(name, email, password);
      setUser(u);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Registrasi gagal';
      setError(msg);
      throw e;
    }
  };

  const logout = () => {
    api.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
