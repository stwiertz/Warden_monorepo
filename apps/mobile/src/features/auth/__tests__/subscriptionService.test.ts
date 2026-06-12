// Tests for subscriptionService.ts under the @react-native-firebase/firestore
// namespaced API (Story 1.7 — Firebase v12 RN migration, Story 3.D).
//
// HOIST NOTE (reused from authService.test.ts / detectionConfigService.test.ts):
// jest hoists jest.mock() factories above the file's imports, AND Babel's
// ES-module compilation hoists `import` → `require()` above the module-scope
// `const mockX = jest.fn()` declarations. So factories run BEFORE those consts
// initialize — a direct `default: mockFn` ref dereferences `undefined`. Every
// factory reference is wrapped in a lazy thunk that defers the deref to call time.
//
// LEAK NOTE: jest 29's `clearAllMocks()` leaves `mockResolvedValueOnce` queues
// intact across tests (observed leak, Story 1.6). Use `resetAllMocks()` then
// re-arm `mockImplementation` in beforeEach.

const mockGet: jest.Mock = jest.fn();
const mockDoc: jest.Mock = jest.fn(() => ({
  get: (...a: unknown[]) => mockGet(...a),
}));
const mockCollection: jest.Mock = jest.fn(() => ({
  doc: (...a: unknown[]) => mockDoc(...a),
}));
const mockFirestoreFn: jest.Mock = jest.fn(() => ({
  collection: (...a: unknown[]) => mockCollection(...a),
}));

jest.mock("@react-native-firebase/firestore", () => {
  // Lazy thunk — see HOIST NOTE. At factory-eval time mockFirestoreFn is
  // undefined; the thunk defers the deref to call time.
  function lazyFirestore(...args: unknown[]): unknown {
    return mockFirestoreFn(...args);
  }
  return { __esModule: true, default: lazyFirestore };
});

const mockSetUser = jest.fn();
// `mock`-prefixed so babel-plugin-jest-hoist allows the factory to close over it.
let mockStoreUser: { uid: string; email: string; isPaid: boolean } | null = null;
jest.mock("../useAuthStore", () => ({
  useAuthStore: {
    getState: () => ({ user: mockStoreUser, setUser: mockSetUser }),
  },
}));

import { subscriptionService } from "../subscriptionService";
import type { FirebaseAuthTypes } from "@react-native-firebase/auth";

const USER = { uid: "user-123" } as unknown as FirebaseAuthTypes.User;

// A Timestamp stand-in matching the duck-typed guard: only `toMillis()` matters.
function ts(ms: number): { toMillis: () => number } {
  return { toMillis: () => ms };
}
// Wide margins so the values stay future/past even after the revalidation tests
// advance jest's fake clock (modern fake timers also fake Date.now()).
const ONE_HUNDRED_DAYS_MS = 100 * 24 * 60 * 60 * 1000;
const FUTURE = ts(Date.now() + ONE_HUNDRED_DAYS_MS);
const PAST = ts(Date.now() - ONE_HUNDRED_DAYS_MS);

// Snapshot fixtures use `exists()` as a METHOD — matches RNFB v24.1.0
// (DocumentSnapshot.exists(): boolean) and the prod code's `userDoc.exists()`.
function snap(exists: boolean, data?: Record<string, unknown>) {
  return { exists: () => exists, data: () => data };
}

beforeEach(() => {
  jest.resetAllMocks();
  mockStoreUser = null;
  // Re-arm the chain after resetAllMocks wiped the implementations.
  mockFirestoreFn.mockImplementation(() => ({
    collection: (...a: unknown[]) => mockCollection(...a),
  }));
  mockCollection.mockImplementation(() => ({
    doc: (...a: unknown[]) => mockDoc(...a),
  }));
  mockDoc.mockImplementation(() => ({
    get: (...a: unknown[]) => mockGet(...a),
  }));
});

describe("checkSubscription — read path (namespaced firestore API)", () => {
  it("reads users/{uid} via firestore().collection().doc().get() — not the JS-SDK getDoc(doc(...)) shape", async () => {
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "active", current_period_end: FUTURE })
    );

    const result = await subscriptionService.checkSubscription(USER);

    expect(mockFirestoreFn).toHaveBeenCalled();
    expect(mockCollection).toHaveBeenCalledWith("users");
    expect(mockDoc).toHaveBeenCalledWith("user-123");
    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(result).toBe(true);
  });

  it("active + future current_period_end → paid (true)", async () => {
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "active", current_period_end: FUTURE })
    );
    expect(await subscriptionService.checkSubscription(USER)).toBe(true);
  });

  it("trialing + future current_period_end → paid (true)", async () => {
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "trialing", current_period_end: FUTURE })
    );
    expect(await subscriptionService.checkSubscription(USER)).toBe(true);
  });

  it("canceled status → not paid (false)", async () => {
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "canceled", current_period_end: FUTURE })
    );
    expect(await subscriptionService.checkSubscription(USER)).toBe(false);
  });

  it("active but current_period_end in the past → not paid (false)", async () => {
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "active", current_period_end: PAST })
    );
    expect(await subscriptionService.checkSubscription(USER)).toBe(false);
  });

  it("missing document (exists() === false) → not paid (false)", async () => {
    mockGet.mockResolvedValueOnce(snap(false));
    expect(await subscriptionService.checkSubscription(USER)).toBe(false);
  });

  it("missing current_period_end → not paid (false)", async () => {
    mockGet.mockResolvedValueOnce(snap(true, { status: "active" }));
    expect(await subscriptionService.checkSubscription(USER)).toBe(false);
  });

  it("non-Timestamp current_period_end (no toMillis) → not paid (false)", async () => {
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "active", current_period_end: 1234567890 })
    );
    expect(await subscriptionService.checkSubscription(USER)).toBe(false);
  });
});

describe("checkSubscription — network-failure fallback (mobile-AUTH-004)", () => {
  it("a failed read falls back to the cached user's isPaid and does NOT throw", async () => {
    mockStoreUser = { uid: "user-123", email: "a@b.c", isPaid: true };
    mockGet.mockRejectedValueOnce(new Error("network down"));

    const result = await subscriptionService.checkSubscription(USER);

    expect(result).toBe(true); // cached isPaid
  });

  it("a failed read with no cached user → false (?? false fallback)", async () => {
    mockStoreUser = null;
    mockGet.mockRejectedValueOnce(new Error("network down"));

    expect(await subscriptionService.checkSubscription(USER)).toBe(false);
  });
});

describe("startPeriodicRevalidation / stopPeriodicRevalidation", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });
  afterEach(() => {
    subscriptionService.stopPeriodicRevalidation();
    jest.useRealTimers();
  });

  it("re-reads on the 60-min interval and calls setUser only when isPaid changes", async () => {
    mockStoreUser = { uid: "user-123", email: "a@b.c", isPaid: false };
    // After the interval fires, the doc reports paid → state should flip.
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "active", current_period_end: FUTURE })
    );

    subscriptionService.startPeriodicRevalidation();
    expect(mockSetUser).not.toHaveBeenCalled();

    jest.advanceTimersByTime(60 * 60 * 1000);
    // Flush the async interval callback's pending microtasks.
    await Promise.resolve();
    await Promise.resolve();

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockSetUser).toHaveBeenCalledWith({
      uid: "user-123",
      email: "a@b.c",
      isPaid: true,
    });
  });

  it("does NOT call setUser when isPaid is unchanged", async () => {
    mockStoreUser = { uid: "user-123", email: "a@b.c", isPaid: true };
    mockGet.mockResolvedValueOnce(
      snap(true, { status: "active", current_period_end: FUTURE })
    );

    subscriptionService.startPeriodicRevalidation();
    jest.advanceTimersByTime(60 * 60 * 1000);
    await Promise.resolve();
    await Promise.resolve();

    expect(mockSetUser).not.toHaveBeenCalled();
  });

  it("swallows a revalidation read error and leaves state unchanged", async () => {
    mockStoreUser = { uid: "user-123", email: "a@b.c", isPaid: true };
    mockGet.mockRejectedValueOnce(new Error("network down"));

    subscriptionService.startPeriodicRevalidation();
    jest.advanceTimersByTime(60 * 60 * 1000);
    await Promise.resolve();
    await Promise.resolve();

    expect(mockSetUser).not.toHaveBeenCalled();
  });

  it("stopPeriodicRevalidation clears the interval (no further reads)", async () => {
    mockStoreUser = { uid: "user-123", email: "a@b.c", isPaid: false };
    mockGet.mockResolvedValue(
      snap(true, { status: "active", current_period_end: FUTURE })
    );

    subscriptionService.startPeriodicRevalidation();
    subscriptionService.stopPeriodicRevalidation();
    jest.advanceTimersByTime(2 * 60 * 60 * 1000);
    await Promise.resolve();

    expect(mockGet).not.toHaveBeenCalled();
  });
});
