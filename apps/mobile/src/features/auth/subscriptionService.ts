import firestore, {
  FirebaseFirestoreTypes,
} from "@react-native-firebase/firestore";
import { type FirebaseAuthTypes } from "@react-native-firebase/auth";
import { useAuthStore } from "./useAuthStore";

const REVALIDATION_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

// Stripe-driven subscription document at users/{uid}. Shape:
//   status: "active" | "trialing" | "canceled" | "past_due" | "incomplete" | ...
//   current_period_end: Timestamp
//   plan, stripe_customer_id, stripe_subscription_id, created_at, updated_at
// We treat `active` and `trialing` as paid, but only while still inside the
// current billing period.
const PAID_STATUSES = new Set(["active", "trialing"]);

function isSubscriptionPaid(data: Record<string, unknown> | undefined): boolean {
  if (!data) return false;
  const status = data.status;
  if (typeof status !== "string" || !PAID_STATUSES.has(status)) return false;
  const periodEnd = data.current_period_end;
  // Story 1.7: duck-type the Timestamp instead of `instanceof Timestamp`. The
  // JS-SDK Timestamp class is gone; the RNFB native module returns a *different*
  // Timestamp class, so `instanceof` the old class would be permanently false
  // (silent paid → not-paid regression). `toMillis()` is the stable contract.
  const toMillis = (periodEnd as FirebaseFirestoreTypes.Timestamp | undefined)
    ?.toMillis;
  if (typeof toMillis !== "function") return false;
  // Validate the return is a real epoch value before comparing — the duck-type
  // accepts any object exposing `toMillis`, so guard against a malformed field
  // (e.g. one returning NaN / a non-number) silently passing the `> now` check.
  const ms = toMillis.call(periodEnd);
  if (typeof ms !== "number" || !Number.isFinite(ms)) return false;
  return ms > Date.now();
}

let revalidationTimer: ReturnType<typeof setInterval> | null = null;

export const subscriptionService = {
  async checkSubscription(user: FirebaseAuthTypes.User): Promise<boolean> {
    try {
      const userDoc = await firestore()
        .collection("users")
        .doc(user.uid)
        .get();
      // RNFB v24.1.0 DocumentSnapshot.exists() is a METHOD (verified against the
      // installed type def — same shape as the JS SDK). Story 1.8 inherits this verdict.
      if (!userDoc.exists()) return false;
      return isSubscriptionPaid(userDoc.data());
    } catch (error) {
      console.warn("[subscription] checkSubscription failed", error);
      const cached = useAuthStore.getState().user;
      return cached?.isPaid ?? false;
    }
  },

  startPeriodicRevalidation(): void {
    this.stopPeriodicRevalidation();
    revalidationTimer = setInterval(async () => {
      const { user, setUser } = useAuthStore.getState();
      if (!user) return;

      try {
        const userDoc = await firestore()
          .collection("users")
          .doc(user.uid)
          .get();
        const isPaid = userDoc.exists()
          ? isSubscriptionPaid(userDoc.data())
          : false;
        if (isPaid !== user.isPaid) {
          setUser({ ...user, isPaid });
        }
      } catch (error) {
        console.warn("[subscription] revalidation failed", error);
      }
    }, REVALIDATION_INTERVAL_MS);
  },

  stopPeriodicRevalidation(): void {
    if (revalidationTimer) {
      clearInterval(revalidationTimer);
      revalidationTimer = null;
    }
  },
};

// --- Six-state entitlement machine (AR-11) ------------------------------------
// Single source of truth for the entitlement state, consumed by Story 3.1's
// derivation logic and Story 3.2's UI. The string union is declared here so
// downstream stories can import it; the implementation is a STUB — Story 3.1
// (AR-11) fills in the real derivation. The 1.7 regression scaffold
// (deriveEntitlementState.test.ts) imports this only so its describe blocks
// compile (assertions are `it.todo`, filled in 3.1).
export type EntitlementState =
  | "paid"
  | "lapsed"
  | "offline-grace ≤30d"
  | "payment-failed"
  | "signed-out";
// Note: `multi-device` is NOT a distinct state — entitlement is per-user, not
// per-device (not enforced per PRD), so it resolves to "paid". The scaffold
// keeps a `multi-device` describe block asserting the "paid" outcome.

export function deriveEntitlementState(
  userDoc: Record<string, unknown> | null | undefined,
  cacheMeta: { isPaid: boolean; cachedAt: number | null; isAuthenticated: boolean },
): EntitlementState {
  // Story 3.1 (AR-11) implements the full derivation; stub here only so the 1.7
  // regression scaffold compiles. Do not rely on this return value yet.
  void userDoc;
  void cacheMeta;
  throw new Error("deriveEntitlementState not implemented until Story 3.1");
}
