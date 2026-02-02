import "./global.css";
import React, { useEffect } from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer } from "@react-navigation/native";
import { RootNavigator } from "./src/app/RootNavigator";
import { authService } from "./src/features/auth/authService";
import { subscriptionService } from "./src/features/auth/subscriptionService";

export default function App() {
  useEffect(() => {
    const unsubscribe = authService.listenToAuthChanges();
    subscriptionService.startPeriodicRevalidation();

    return () => {
      unsubscribe();
      subscriptionService.stopPeriodicRevalidation();
    };
  }, []);

  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <RootNavigator />
    </NavigationContainer>
  );
}
