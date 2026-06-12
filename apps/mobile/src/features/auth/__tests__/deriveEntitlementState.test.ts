// Six-state entitlement regression SCAFFOLD (Story 1.7 / Story 3.D).
//
// One `describe` block per entitlement state. These are intentionally
// `it.todo(...)` placeholders — Story 3.1 (AR-11) implements
// `deriveEntitlementState` and fills in the real assertions. The import below
// exists only to prove the stub's type/signature resolves so this file compiles
// and participates in the suite count now.
//
// State rules mirror the Gherkin in epics-and-stories.md:1342-1374 and
// architecture.md:776, 793-796. Do NOT add real expectations here.

// subscriptionService imports the RNFB firestore native module at the top
// level; stub it so this pure-function scaffold doesn't try to load native code.
jest.mock("@react-native-firebase/firestore", () => ({
  __esModule: true,
  default: jest.fn(),
}));

import { deriveEntitlementState } from "../subscriptionService";

// Reference the import so the scaffold fails to compile if the stub's export is
// removed/renamed before Story 3.1 lands (without invoking it — the stub throws).
// Kept inside an `it` so the assertion runs as a named test rather than at
// jest collection time.
describe("deriveEntitlementState — stub contract", () => {
  it("is exported as a function", () => {
    expect(typeof deriveEntitlementState).toBe("function");
  });
});

describe("deriveEntitlementState — paid", () => {
  it.todo("active status with current_period_end in the future → 'paid'");
  it.todo("trialing status with current_period_end in the future → 'paid'");
});

describe("deriveEntitlementState — lapsed", () => {
  it.todo("canceled status → 'lapsed'");
  it.todo("current_period_end in the past → 'lapsed'");
  it.todo("past_due beyond the payment-failed grace period → 'lapsed'");
});

describe("deriveEntitlementState — offline-grace ≤30d", () => {
  it.todo(
    "read failed, cached isPaid=true, cachedAt within the last 30 days → 'offline-grace ≤30d'"
  );
});

describe("deriveEntitlementState — payment-failed", () => {
  it.todo(
    "past_due within paymentFailedGracePeriodMs (default 7d) → 'payment-failed'"
  );
});

describe("deriveEntitlementState — multi-device", () => {
  // Not a distinct state: entitlement is per-user, not per-device → resolves to 'paid'.
  it.todo("same paid user observed on a second device → 'paid'");
});

describe("deriveEntitlementState — signed-out", () => {
  it.todo("no auth token → 'signed-out'");
  it.todo("read failed and cache stale (>30d) → 'signed-out'");
});
