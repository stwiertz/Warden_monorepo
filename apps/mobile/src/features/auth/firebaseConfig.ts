import { initializeApp, getApps, getApp } from "firebase/app";

// Auth runs on @react-native-firebase/auth (native session persistence via the
// Android Keystore — no JS-side init needed). The native [DEFAULT] app
// auto-initializes from google-services.json, so auth consumers import `auth`
// from "@react-native-firebase/auth" directly (see authService.ts /
// googleSignInService.ts). The old firebase/auth `initializeAuth` +
// `getReactNativePersistence(AsyncStorage)` wiring is gone (Story 1.5).
//
// This firebase/app (JS SDK) initialization is retained ONLY as a transitional
// shim to keep the `app` export alive for the still-JS-SDK Firestore consumers
// (subscriptionService → Story 1.7, detectionConfigService → Story 1.8). It is
// removed in Story 1.8 once the last Firestore consumer migrates to
// @react-native-firebase/firestore.
const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY ?? "",
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID ?? "",
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID ?? "",
};

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

export { app };
