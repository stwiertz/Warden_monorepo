/**
 * Types for auth & subscription feature (FR29-33).
 */

export interface AuthState {
  isAuthenticated: boolean;
  userId: string | null;
  isPaid: boolean;
  lastValidatedAt: string | null;
}

export const AUTH_CACHE_VALIDITY_DAYS = 30;
