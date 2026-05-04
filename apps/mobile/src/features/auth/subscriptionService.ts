import { getFirestore, doc, getDoc, Timestamp } from "firebase/firestore";
import { type User } from "firebase/auth";
import { app } from "./firebaseConfig";
import { useAuthStore } from "./useAuthStore";

const firestore = getFirestore(app);
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
  if (!(periodEnd instanceof Timestamp)) return false;
  return periodEnd.toMillis() > Date.now();
}

let revalidationTimer: ReturnType<typeof setInterval> | null = null;

export const subscriptionService = {
  async checkSubscription(user: User): Promise<boolean> {
    try {
      const userDoc = await getDoc(doc(firestore, "users", user.uid));
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
        const userDoc = await getDoc(doc(firestore, "users", user.uid));
        const isPaid = userDoc.exists() ? isSubscriptionPaid(userDoc.data()) : false;
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
