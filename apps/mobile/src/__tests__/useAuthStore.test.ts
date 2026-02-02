import { useAuthStore, type AuthUser } from "../features/auth/useAuthStore";

// Reset store before each test
beforeEach(() => {
  useAuthStore.setState({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    cachedAt: null,
  });
});

describe("useAuthStore", () => {
  it("starts with unauthenticated state", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("setUser with paid user sets isAuthenticated true and clears isLoading", () => {
    useAuthStore.getState().setLoading(true);
    expect(useAuthStore.getState().isLoading).toBe(true);

    const user: AuthUser = { uid: "u1", email: "a@b.com", isPaid: true };
    useAuthStore.getState().setUser(user);

    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
    expect(state.cachedAt).toBeGreaterThan(0);
  });

  it("setUser with non-paid user sets isAuthenticated false", () => {
    const user: AuthUser = { uid: "u2", email: "b@c.com", isPaid: false };
    useAuthStore.getState().setUser(user);

    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
    expect(state.isAuthenticated).toBe(false);
  });

  it("setUser with null clears auth state", () => {
    const user: AuthUser = { uid: "u1", email: "a@b.com", isPaid: true };
    useAuthStore.getState().setUser(user);
    useAuthStore.getState().setUser(null);

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.cachedAt).toBeNull();
  });

  it("setError clears isLoading", () => {
    useAuthStore.getState().setLoading(true);
    useAuthStore.getState().setError("Something failed");

    const state = useAuthStore.getState();
    expect(state.error).toBe("Something failed");
    expect(state.isLoading).toBe(false);
  });

  it("logout resets all auth fields", () => {
    const user: AuthUser = { uid: "u1", email: "a@b.com", isPaid: true };
    useAuthStore.getState().setUser(user);
    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.cachedAt).toBeNull();
  });
});
