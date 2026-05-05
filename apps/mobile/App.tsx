import "./global.css";
import React, { useEffect } from "react";
import { View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { NavigationContainer } from "@react-navigation/native";
import {
  useFonts,
  Roboto_400Regular,
  Roboto_500Medium,
  Roboto_700Bold,
} from "@expo-google-fonts/roboto";
import {
  JetBrainsMono_400Regular,
  JetBrainsMono_500Medium,
  JetBrainsMono_700Bold,
} from "@expo-google-fonts/jetbrains-mono";
import { RootNavigator } from "./src/app/RootNavigator";
import { authService } from "./src/features/auth/authService";
import { subscriptionService } from "./src/features/auth/subscriptionService";
import { googleSignInService } from "./src/features/auth/googleSignInService";
import { useAuthStore } from "./src/features/auth/useAuthStore";
import { bootstrapDetectionConfig } from "./src/features/video-processing/detectionConfigBootstrap";

// DEV ONLY: bypasses login + subscription gate so the rest of the app can be
// worked on without a working Firebase/Stripe wiring. Remove this branch (and
// the EXPO_PUBLIC_AUTH_BYPASS env var) once the real auth flow is in place.
const AUTH_BYPASS = process.env.EXPO_PUBLIC_AUTH_BYPASS === "true";

export default function App() {
  const [fontsLoaded] = useFonts({
    Roboto_400Regular,
    Roboto_500Medium,
    Roboto_700Bold,
    JetBrainsMono_400Regular,
    JetBrainsMono_500Medium,
    JetBrainsMono_700Bold,
  });

  useEffect(() => {
    void bootstrapDetectionConfig();

    if (AUTH_BYPASS) {
      console.warn(
        "[auth] EXPO_PUBLIC_AUTH_BYPASS is enabled — login and subscription checks are skipped."
      );
      useAuthStore.getState().setUser({
        uid: "dev-bypass-user",
        email: "dev@warden.local",
        isPaid: true,
      });
      return;
    }

    googleSignInService.configure();
    const unsubscribe = authService.listenToAuthChanges();
    subscriptionService.startPeriodicRevalidation();

    return () => {
      unsubscribe();
      subscriptionService.stopPeriodicRevalidation();
    };
  }, []);

  if (!fontsLoaded) {
    return <View style={{ flex: 1, backgroundColor: "#0a0a0d" }} />;
  }

  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <StatusBar style="light" />
        <RootNavigator />
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
