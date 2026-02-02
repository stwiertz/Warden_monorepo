import { getFirestore, doc, getDoc } from "firebase/firestore";
import { type User } from "firebase/auth";
import { app } from "./firebaseConfig";
import { useAuthStore } from "./useAuthStore";

const firestore = getFirestore(app);
const REVALIDATION_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

let revalidationTimer: ReturnType<typeof setInterval> | null = null;

export const subscriptionService = {
  async checkSubscription(user: User): Promise<boolean> {
    try {
      const userDoc = await getDoc(doc(firestore, "users", user.uid));
      if (!userDoc.exists()) return false;
      const data = userDoc.data();
      return data?.isPaid === true;
    } catch {
      // If offline or error, fall back to cached state
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
        if (!userDoc.exists()) {
          setUser({ ...user, isPaid: false });
          return;
        }
        const data = userDoc.data();
        const isPaid = data?.isPaid === true;
        if (isPaid !== user.isPaid) {
          setUser({ ...user, isPaid });
        }
      } catch {
        // Offline - keep cached state
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
