import auth, { type FirebaseAuthTypes } from "@react-native-firebase/auth";
import { useAuthStore, type AuthUser } from "./useAuthStore";
import { subscriptionService } from "./subscriptionService";

export async function mapFirebaseUser(
  user: FirebaseAuthTypes.User
): Promise<AuthUser> {
  // Cross-SDK seam (transitional): subscriptionService still types its param as
  // the firebase/auth (JS SDK) `User` and reads only `.uid`. The RNFB user is
  // structurally compatible for that read but is nominally a different SDK type
  // (missing refreshToken/tenantId). This bridge is removed in Story 1.7 when
  // subscriptionService migrates to @react-native-firebase/firestore + RNFB user.
  const isPaid = await subscriptionService.checkSubscription(
    user as unknown as Parameters<
      typeof subscriptionService.checkSubscription
    >[0]
  );
  // TODO(Story 2.3 — Epic 2 telemetry wrapper): emit T0 here when mapFirebaseUser
  // confirms isPaid === true (first paid auth-state-change in session). Payload
  // contract per epics-and-stories.md:1218-1247: { elapsed_seconds, t0_at, t1_path? }.
  // NO frame/audio data (PRIV-001/002). Story 2.2 lands the analytics wrapper;
  // Story 2.3 replaces this comment with the emit call.
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
      const credential = await auth().signInWithEmailAndPassword(
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
    await auth().signOut();
    logout();
  },

  listenToAuthChanges(): () => void {
    return auth().onAuthStateChanged(async (user) => {
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
