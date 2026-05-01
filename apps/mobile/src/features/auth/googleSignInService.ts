import {
  GoogleSignin,
  statusCodes,
} from "@react-native-google-signin/google-signin";
import { GoogleAuthProvider, signInWithCredential } from "firebase/auth";
import { auth } from "./firebaseConfig";
import { useAuthStore } from "./useAuthStore";
import { mapFirebaseUser } from "./authService";

let configured = false;

export const googleSignInService = {
  configure(): void {
    if (configured) return;
    const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;
    if (!webClientId) {
      // Fail loudly in dev — the native sign-in call will throw a less
      // obvious error otherwise.
      console.warn(
        "EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID is not set. Google sign-in will fail."
      );
    }
    GoogleSignin.configure({ webClientId });
    configured = true;
  },

  async loginWithGoogle(): Promise<void> {
    const { setLoading, setUser, setError } = useAuthStore.getState();
    setLoading(true);
    try {
      await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
      const result = await GoogleSignin.signIn();
      const idToken = extractIdToken(result);
      if (!idToken) {
        setError("Google sign-in did not return an ID token. Please try again.");
        return;
      }
      const credential = GoogleAuthProvider.credential(idToken);
      const firebaseCredential = await signInWithCredential(auth, credential);
      const authUser = await mapFirebaseUser(firebaseCredential.user);
      setUser(authUser);
      if (!authUser.isPaid) {
        setError(
          "Your subscription is inactive. Please subscribe to access Warden."
        );
      }
    } catch (error: unknown) {
      handleGoogleSignInError(error, setError, setLoading);
    }
  },

  async signOut(): Promise<void> {
    try {
      await GoogleSignin.signOut();
    } catch {
      // Best-effort — Firebase signOut is the source of truth for app auth.
    }
  },
};

// google-signin returns either { idToken, ... } (v12-) or { data: { idToken, ... } } (v13+)
type SignInLikeResult = {
  idToken?: string | null;
  data?: { idToken?: string | null } | null;
};

function extractIdToken(result: SignInLikeResult): string | null {
  return result?.data?.idToken ?? result?.idToken ?? null;
}

function handleGoogleSignInError(
  error: unknown,
  setError: (msg: string | null) => void,
  setLoading: (loading: boolean) => void
): void {
  const code = (error as { code?: string | number } | null)?.code;
  const message = error instanceof Error ? error.message : String(error);
  console.warn("[googleSignIn] failed", { code, message, error });

  if (code === statusCodes.SIGN_IN_CANCELLED) {
    setLoading(false);
    return;
  }
  if (code === statusCodes.IN_PROGRESS) {
    setLoading(false);
    return;
  }
  if (code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
    setError("Google Play Services is not available on this device.");
    return;
  }
  if (message.includes("auth/account-exists-with-different-credential")) {
    setError(
      "An account already exists with this email using a different sign-in method."
    );
    return;
  }
  if (message.includes("auth/network-request-failed")) {
    setError("Network error. Check your connection.");
    return;
  }
  // Surface the underlying code/message in the toast itself so we don't have
  // to chase logs while the integration is still being wired up. Trim once
  // the flow is verified.
  const codeStr = code !== undefined ? ` [${code}]` : "";
  setError(`Google sign-in failed${codeStr}: ${message}`);
}
