import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { zustandMMKVStorage } from "../../shared/services/storage";

export interface AuthUser {
  uid: string;
  email: string;
  isPaid: boolean;
}

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  cachedAt: number | null;
  setUser: (user: AuthUser | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  logout: () => void;
}

const AUTH_CACHE_DURATION_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      cachedAt: null,
      setUser: (user) =>
        set({
          user,
          isAuthenticated: user !== null && user.isPaid,
          isLoading: false,
          error: null,
          cachedAt: user ? Date.now() : null,
        }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error, isLoading: false }),
      logout: () =>
        set({
          user: null,
          isAuthenticated: false,
          error: null,
          cachedAt: null,
        }),
    }),
    {
      name: "auth-store",
      storage: createJSONStorage(() => zustandMMKVStorage),
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        cachedAt: state.cachedAt,
      }),
      onRehydrateStorage: () => (state) => {
        // Invalidate cache if older than 30 days
        if (state?.cachedAt) {
          const elapsed = Date.now() - state.cachedAt;
          if (elapsed > AUTH_CACHE_DURATION_MS) {
            state.user = null;
            state.isAuthenticated = false;
            state.cachedAt = null;
          }
        }
      },
    }
  )
);
