/**
 * Auth Zustand store.
 * Syncs with Firebase onAuthStateChanged.
 * Fetches user profile (tenantId, role) from /api/v1/auth/me on login.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User as FirebaseUser } from "firebase/auth";

interface AuthState {
  user: FirebaseUser | null;
  tenantId: string | null;
  role: string;
  permissions: string[];
  isLoading: boolean;
  isInitialized: boolean;
  displayName: string | null;

  setUser: (user: FirebaseUser | null) => void;
  setProfile: (profile: {
    tenantId: string;
    role: string;
    permissions: string[];
    displayName?: string | null;
  }) => void;
  setLoading: (loading: boolean) => void;
  setInitialized: () => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      tenantId: null,
      role: "AGENT_OPERATOR",
      permissions: [],
      isLoading: true,
      isInitialized: false,
      displayName: null,

      setUser: (user) =>
        set({
          user,
          isLoading: false,
          displayName: user?.displayName ?? null,
        }),

      setProfile: (profile) =>
        set({
          tenantId: profile.tenantId,
          role: profile.role,
          permissions: profile.permissions,
          displayName: profile.displayName ?? null,
          isLoading: false,
        }),

      setLoading: (loading) => set({ isLoading: loading }),

      setInitialized: () => set({ isInitialized: true }),

      logout: () =>
        set({
          user: null,
          tenantId: null,
          role: "AGENT_OPERATOR",
          permissions: [],
          isLoading: false,
          displayName: null,
        }),
    }),
    {
      name: "antigravity-auth",
      partialize: (state) => ({
        tenantId: state.tenantId,
        role: state.role,
        permissions: state.permissions,
        displayName: state.displayName,
      }),
    }
  )
);
