// Tests for authService.ts under the @react-native-firebase/auth namespaced API
// (Story 1.5 / 1.6 — Firebase v12 RN auth migration, Story 3.C).
//
// HOIST NOTE: jest hoists jest.mock() factories above the file's imports, AND
// Babel's ES-module compilation hoists `import` → `require()` calls above the
// `const` declarations. Net effect: factories run BEFORE the module-scope
// `const mockX = jest.fn()` declarations execute. So any direct reference like
// `default: mockAuthFn` inside a factory dereferences `undefined`. Wrap every
// factory reference in a lazy thunk that defers the deref to call time
// (precedent: `detectionConfigService.test.ts:9` — `getDoc: (...args) => mockGetDoc(...args)`).

// Type the mocks as jest.Mock so the factory's spread thunks don't trip on
// jest.fn's inferred zero-arg signature (and so babel-plugin-jest-hoist doesn't
// see inline type-parameter names as free variables).
const mockSignInWithEmailAndPassword: jest.Mock = jest.fn();
const mockSignOut: jest.Mock = jest.fn();
const mockOnAuthStateChanged: jest.Mock = jest.fn();
const mockSignInWithCredential: jest.Mock = jest.fn();
const mockGoogleAuthProviderCredential: jest.Mock = jest.fn();
const mockAuthInstance = {
  signInWithEmailAndPassword: mockSignInWithEmailAndPassword,
  signOut: mockSignOut,
  onAuthStateChanged: mockOnAuthStateChanged,
  signInWithCredential: mockSignInWithCredential,
};
const mockAuthFn: jest.Mock = jest.fn(() => mockAuthInstance);

jest.mock("@react-native-firebase/auth", () => {
  // Lazy thunks — see HOIST NOTE above. At factory-eval time mockAuthFn et al
  // are undefined; the thunks defer the deref to call time.
  function lazyAuth(...args: unknown[]): unknown {
    return mockAuthFn(...args);
  }
  // Static attached to the callable singleton — `auth.GoogleAuthProvider.credential`.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (lazyAuth as any).GoogleAuthProvider = {
    credential: function credential(...args: unknown[]): unknown {
      return mockGoogleAuthProviderCredential(...args);
    },
  };
  return { __esModule: true, default: lazyAuth };
});

const mockCheckSubscription = jest.fn();
jest.mock("../subscriptionService", () => ({
  subscriptionService: {
    checkSubscription: (...args: unknown[]) => mockCheckSubscription(...args),
  },
}));

const mockSetLoading = jest.fn();
const mockSetUser = jest.fn();
const mockSetError = jest.fn();
const mockStoreLogout = jest.fn();
jest.mock("../useAuthStore", () => ({
  useAuthStore: {
    getState: () => ({
      setLoading: mockSetLoading,
      setUser: mockSetUser,
      setError: mockSetError,
      logout: mockStoreLogout,
    }),
  },
}));

import { authService, mapFirebaseUser } from "../authService";
import type { FirebaseAuthTypes } from "@react-native-firebase/auth";

function makeUser(
  overrides: Partial<FirebaseAuthTypes.User> = {}
): FirebaseAuthTypes.User {
  return {
    uid: "user-123",
    email: "test@example.com",
    ...overrides,
  } as unknown as FirebaseAuthTypes.User;
}

beforeEach(() => {
  // resetAllMocks wipes call data AND impl/queues (clearAllMocks leaves
  // mockResolvedValueOnce queues intact across tests — observed leak). After
  // reset, re-arm mockAuthFn so `auth()` keeps returning the shared instance.
  jest.resetAllMocks();
  mockAuthFn.mockImplementation(() => mockAuthInstance);
});

describe("authService.login (namespaced API)", () => {
  it("calls auth().signInWithEmailAndPassword(email, password) — not the JS-SDK first-arg shape", async () => {
    mockSignInWithEmailAndPassword.mockResolvedValueOnce({ user: makeUser() });
    mockCheckSubscription.mockResolvedValueOnce(true);

    await authService.login("test@example.com", "secret");

    expect(mockAuthFn).toHaveBeenCalled();
    expect(mockSignInWithEmailAndPassword).toHaveBeenCalledWith(
      "test@example.com",
      "secret"
    );
    // Regression pin: NOT the legacy `signInWithEmailAndPassword(auth, email, password)` shape.
    expect(mockSignInWithEmailAndPassword).not.toHaveBeenCalledWith(
      mockAuthInstance,
      "test@example.com",
      "secret"
    );
  });

  it("on success with isPaid=true, calls setUser with the mapped AuthUser and does not call setError", async () => {
    const user = makeUser({ uid: "u-1", email: "alice@example.com" });
    mockSignInWithEmailAndPassword.mockResolvedValueOnce({ user });
    mockCheckSubscription.mockResolvedValueOnce(true);

    await authService.login("alice@example.com", "secret");

    expect(mockCheckSubscription).toHaveBeenCalledTimes(1);
    expect(mockSetUser).toHaveBeenCalledWith({
      uid: "u-1",
      email: "alice@example.com",
      isPaid: true,
    });
    expect(mockSetError).not.toHaveBeenCalled();
  });

  it("when isPaid===false, still calls setUser but also calls setError with the inactive-subscription message", async () => {
    mockSignInWithEmailAndPassword.mockResolvedValueOnce({ user: makeUser() });
    mockCheckSubscription.mockResolvedValueOnce(false);

    await authService.login("test@example.com", "secret");

    expect(mockSetUser).toHaveBeenCalledWith(
      expect.objectContaining({ isPaid: false })
    );
    expect(mockSetError).toHaveBeenCalledWith(
      "Your subscription is inactive. Please subscribe to access Warden."
    );
  });

  it("on a Firebase auth/invalid-credential error, calls setError with the formatAuthError mapping", async () => {
    mockSignInWithEmailAndPassword.mockRejectedValueOnce(
      new Error("Firebase: Error (auth/invalid-credential).")
    );

    await authService.login("test@example.com", "wrong");

    expect(mockSetUser).not.toHaveBeenCalled();
    expect(mockSetError).toHaveBeenCalledWith("Invalid email or password");
  });
});

describe("authService.logout (namespaced API)", () => {
  it("awaits auth().signOut() then calls the store's logout()", async () => {
    mockSignOut.mockResolvedValueOnce(undefined);

    await authService.logout();

    expect(mockSignOut).toHaveBeenCalledTimes(1);
    expect(mockStoreLogout).toHaveBeenCalledTimes(1);
    const signOutOrder = mockSignOut.mock.invocationCallOrder[0];
    const logoutOrder = mockStoreLogout.mock.invocationCallOrder[0];
    expect(signOutOrder).toBeLessThan(logoutOrder);
  });
});

describe("authService.listenToAuthChanges (namespaced API)", () => {
  it("calls auth().onAuthStateChanged with a function and returns the unsubscribe", () => {
    const mockUnsubscribe = jest.fn();
    mockOnAuthStateChanged.mockReturnValueOnce(mockUnsubscribe);

    const unsubscribe = authService.listenToAuthChanges();

    expect(mockOnAuthStateChanged).toHaveBeenCalledTimes(1);
    expect(typeof mockOnAuthStateChanged.mock.calls[0][0]).toBe("function");
    expect(unsubscribe).toBe(mockUnsubscribe);
  });

  it("callback invoked with a user → calls setUser with the mapped AuthUser", async () => {
    const mockUnsubscribe = jest.fn();
    mockOnAuthStateChanged.mockReturnValueOnce(mockUnsubscribe);
    mockCheckSubscription.mockResolvedValueOnce(true);

    authService.listenToAuthChanges();
    const callback = mockOnAuthStateChanged.mock.calls[0][0] as (
      u: FirebaseAuthTypes.User | null
    ) => Promise<void>;
    await callback(makeUser({ uid: "u-9", email: "bob@example.com" }));

    expect(mockSetUser).toHaveBeenCalledWith({
      uid: "u-9",
      email: "bob@example.com",
      isPaid: true,
    });
  });

  it("callback invoked with null → calls setUser(null) and skips checkSubscription", async () => {
    const mockUnsubscribe = jest.fn();
    mockOnAuthStateChanged.mockReturnValueOnce(mockUnsubscribe);

    authService.listenToAuthChanges();
    const callback = mockOnAuthStateChanged.mock.calls[0][0] as (
      u: FirebaseAuthTypes.User | null
    ) => Promise<void>;
    await callback(null);

    expect(mockSetUser).toHaveBeenCalledWith(null);
    expect(mockCheckSubscription).not.toHaveBeenCalled();
  });
});

describe("mapFirebaseUser (cross-SDK seam — removed in Story 1.7)", () => {
  it("calls subscriptionService.checkSubscription with the user and returns {uid, email, isPaid}", async () => {
    const user = makeUser({ uid: "u-77", email: "carol@example.com" });
    mockCheckSubscription.mockResolvedValueOnce(true);

    const result = await mapFirebaseUser(user);

    expect(mockCheckSubscription).toHaveBeenCalledTimes(1);
    expect(mockCheckSubscription).toHaveBeenCalledWith(user);
    expect(result).toEqual({
      uid: "u-77",
      email: "carol@example.com",
      isPaid: true,
    });
  });

  it("falls back to email:'' when user.email is null", async () => {
    const user = makeUser({
      uid: "u-null-email",
      email: null as unknown as string,
    });
    mockCheckSubscription.mockResolvedValueOnce(false);

    const result = await mapFirebaseUser(user);

    expect(result).toEqual({
      uid: "u-null-email",
      email: "",
      isPaid: false,
    });
  });
});
