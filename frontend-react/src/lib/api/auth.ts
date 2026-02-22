import { api } from './client';
import { setSession, clearSession } from '../auth/session';

export interface MeResponse {
  success: boolean;
  auth_required?: boolean;
  user: {
    id: string;
    email?: string | null;
    role: 'admin' | 'user' | string;
    is_admin: boolean;
    is_authenticated: boolean;
  };
}

export interface AuthResponse {
  success: boolean;
  user?: {
    id: string;
    email?: string | null;
  };
  session?: {
    access_token?: string | null;
    refresh_token?: string | null;
    expires_in?: number | null;
    token_type?: string | null;
  };
  error?: string;
}

export const authAPI = {
  async me(): Promise<MeResponse> {
    const response = await api.get('/auth/me');
    return response.data as MeResponse;
  },

  async signIn(email: string, password: string): Promise<AuthResponse> {
    try {
      const response = await api.post('/auth/signin', { email, password });
      const data = response.data as AuthResponse;
      if (data?.session?.access_token) {
        setSession(data.session.access_token, data.session.refresh_token);
      }
      return data;
    } catch (err: any) {
      const message =
        err?.response?.data?.error ||
        err?.response?.data?.message ||
        err?.message ||
        'Sign in failed';
      return { success: false, error: message };
    }
  },

  async signUp(email: string, password: string): Promise<AuthResponse> {
    try {
      const response = await api.post('/auth/signup', { email, password });
      const data = response.data as AuthResponse;
      if (data?.session?.access_token) {
        setSession(data.session.access_token, data.session.refresh_token);
      }
      return data;
    } catch (err: any) {
      const message =
        err?.response?.data?.error ||
        err?.response?.data?.message ||
        err?.message ||
        'Sign up failed';
      return { success: false, error: message };
    }
  },

  async signOut(): Promise<void> {
    try {
      await api.post('/auth/signout');
    } finally {
      clearSession();
    }
  },
};
