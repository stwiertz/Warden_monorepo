import { initializeApp, getApps, getApp } from "firebase/app";
import {
  initializeAuth,
  getAuth,
  getReactNativePersistence,
} from "firebase/auth";
import ReactNativeAsyncStorage from "@react-native-async-storage/async-storage";

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY ?? "",
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID ?? "",
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID ?? "",
};

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

// Use AsyncStorage for auth persistence on React Native.
// The default web SDK persistence (indexedDB/localStorage) does not exist in RN.
// TODO: Consider migrating to @react-native-firebase/* native SDK for better
// performance, native token refresh, and full offline auth support.
const auth =
  getApps().length === 1
    ? initializeAuth(app, {
        persistence: getReactNativePersistence(ReactNativeAsyncStorage),
      })
    : getAuth(app);

export { app, auth };
