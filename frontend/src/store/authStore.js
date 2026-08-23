import { create } from 'zustand';
import { api } from '../lib/api';

export const useAuthStore = create((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,
  directReports: [],

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
      directReports: [],
    });
  },

  fetchDirectReports: async () => {
    try {
      const res = await api.get('/users/me/reports');
      const reports = res.data || [];
      set({ directReports: reports });
      return reports;
    } catch {
      set({ directReports: [] });
      return [];
    }
  },

  login: async (employeeCode, password) => {
    // 1. Authenticate credentials
    const loginRes = await api.post('/auth/login', { employee_code: employeeCode, password });
    const { access_token, must_change_password, user: loginUser } = loginRes.data;

    // 2. Set token in memory temporarily so subsequent calls read it
    set({ accessToken: access_token });

    let userData = loginUser;

    if (!userData) {
      try {
        const userRes = await api.get('/users/me');
        userData = userRes.data;
      } catch (err) {
        if (err.response?.data?.detail === 'password_change_required' || must_change_password) {
          userData = { employee_code: employeeCode, must_change_password: true };
        } else {
          throw err;
        }
      }
    }

    if (must_change_password !== undefined) {
      userData = { ...userData, must_change_password };
    }

    set({
      user: userData,
      accessToken: access_token,
      isAuthenticated: true,
      isLoading: false,
    });

    if (!userData.must_change_password) {
      await get().fetchDirectReports();
    }

    return userData;
  },

  changePassword: async (currentPassword, newPassword) => {
    const res = await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    const updatedUser = res.data;
    set({
      user: updatedUser,
      isAuthenticated: true,
    });
    if (!updatedUser.must_change_password) {
      await get().fetchDirectReports();
    }
    return updatedUser;
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
      try {
        const userRes = await api.get('/users/me');
        console.log('[authStore] GET /users/me user profile:', userRes.data);
        const userData = userRes.data;

        set({
          user: userData,
          accessToken: token,
          isAuthenticated: true,
          isLoading: false,
        });

        if (!userData.must_change_password) {
          await get().fetchDirectReports();
        }

        return true;
      } catch (userErr) {
        if (userErr.response?.data?.detail === 'password_change_required') {
          console.log('[authStore] User must change password before accessing profile');
          set({
            user: { must_change_password: true },
            accessToken: token,
            isAuthenticated: true,
            isLoading: false,
            directReports: [],
          });
          return true;
        }
        throw userErr;
      }
    } catch (err) {
      console.error('[authStore] refreshSession failed with error:', err.response?.status, err.response?.data || err.message);
      get().clearAuth();
      return false;
    }
  },
}));
