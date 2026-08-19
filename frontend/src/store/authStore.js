import { create } from 'zustand';
import { api } from '../lib/api';

export const useAuthStore = create((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,

  setAccessToken: (token) => {
    set({
      accessToken: token,
      isAuthenticated: Boolean(get().user && token),
    });
  },

  clearAuth: () => {
    set({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  login: async (email, password) => {
    // 1. Authenticate credentials
    const loginRes = await api.post('/auth/login', { email, password });
    const token = loginRes.data.access_token;

    // 2. Set token in memory temporarily so /users/me can read it
    set({ accessToken: token });

    // 3. Fetch user profile
    const userRes = await api.get('/users/me');
    const userData = userRes.data;

    set({
      user: userData,
      accessToken: token,
      isAuthenticated: true,
      isLoading: false,
    });

    return userData;
  },

  register: async (full_name, email, password) => {
    const registerRes = await api.post('/auth/register', {
      full_name,
      email,
      password,
    });
    return registerRes.data;
  },

  logout: async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // Ignore logout errors, clear client state regardless
    } finally {
      get().clearAuth();
    }
  },

  refreshSession: async () => {
    console.log('[authStore] Starting refreshSession()...');
    set({ isLoading: true });
    try {
      // 1. Silent refresh call using httpOnly cookie
      console.log('[authStore] Sending POST /auth/refresh...');
      const refreshRes = await api.post('/auth/refresh');
      console.log('[authStore] POST /auth/refresh response received:', refreshRes.data);
      const token = refreshRes.data.access_token;

      if (!token) {
        console.log('[authStore] No token returned in refresh response, clearing auth');
        get().clearAuth();
        return false;
      }

      set({ accessToken: token });

      // 2. Fetch authenticated user profile
      console.log('[authStore] Fetching GET /users/me...');
      const userRes = await api.get('/users/me');
      console.log('[authStore] GET /users/me user profile:', userRes.data);
      const userData = userRes.data;

      set({
        user: userData,
        accessToken: token,
        isAuthenticated: true,
        isLoading: false,
      });

      return true;
    } catch (err) {
      console.error('[authStore] refreshSession failed with error:', err.response?.status, err.response?.data || err.message);
      get().clearAuth();
      return false;
    }
  },
}));
