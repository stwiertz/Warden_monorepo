import {
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  type User,
} from "firebase/auth";
import { auth } from "./firebaseConfig";
import { useAuthStore, type AuthUser } from "./useAuthStore";
import { subscriptionService } from "./subscriptionService";

export async function mapFirebaseUser(user: User): Promise<AuthUser> {
  const isPaid = await subscriptionService.checkSubscription(user);
  return {
    uid: user.uid,
    email: user.email ?? "",
    isPaid,
  };
}

export const authService = {
  async login(email: string, password: string): Promise<void> {
    const { setLoading, setUser, setError } = useAuthStore.getState();
    setLoading(true);
    try {
      const credential = await signInWithEmailAndPassword(
        auth,
        email,
        password
      );
      const authUser = await mapFirebaseUser(credential.user);
      setUser(authUser);
      if (!authUser.isPaid) {
        setError("Your subscription is inactive. Please subscribe to access Warden.");
      }
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "Login failed";
      setError(formatAuthError(message));
    }
  },

  async logout(): Promise<void> {
    const { logout } = useAuthStore.getState();
    await signOut(auth);
    logout();
  },

  listenToAuthChanges(): () => void {
    return onAuthStateChanged(auth, async (user) => {
      const { setUser } = useAuthStore.getState();
      if (user) {
        const authUser = await mapFirebaseUser(user);
        setUser(authUser);
      } else {
        setUser(null);
      }
    });
  },
};

function formatAuthError(message: string): string {
  if (message.includes("auth/invalid-email")) return "Invalid email address";
  if (message.includes("auth/user-disabled")) return "This account has been disabled";
  if (message.includes("auth/user-not-found")) return "No account found with this email";
  if (message.includes("auth/wrong-password")) return "Incorrect password";
  if (message.includes("auth/invalid-credential")) return "Invalid email or password";
  if (message.includes("auth/too-many-requests")) return "Too many attempts. Try again later";
  if (message.includes("auth/network-request-failed")) return "Network error. Check your connection";
  return "Login failed. Please try again";
}
