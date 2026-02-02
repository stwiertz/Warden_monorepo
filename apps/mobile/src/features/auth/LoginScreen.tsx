import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Button, Toast } from "../../shared/components";
import { useAuthStore } from "./useAuthStore";
import { authService } from "./authService";

export function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { isLoading, error, setError } = useAuthStore();

  const handleLogin = useCallback(() => {
    if (!email.trim() || !password.trim()) {
      setError("Please enter email and password");
      return;
    }
    authService.login(email.trim(), password);
  }, [email, password, setError]);

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      className="flex-1 bg-background"
    >
      <View className="flex-1 justify-center px-6">
        <Text className="text-accent text-heading font-bold text-center mb-2">
          Warden
        </Text>
        <Text className="text-text-secondary text-body text-center mb-10">
          Sign in to continue
        </Text>

        <TextInput
          className="bg-surface text-text-primary text-body rounded-lg px-4 py-3 mb-4 min-h-[44px]"
          placeholder="Email"
          placeholderTextColor="#8B8F96"
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          value={email}
          onChangeText={setEmail}
        />

        <TextInput
          className="bg-surface text-text-primary text-body rounded-lg px-4 py-3 mb-6 min-h-[44px]"
          placeholder="Password"
          placeholderTextColor="#8B8F96"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <Button title="Sign in" loading={isLoading} onPress={handleLogin} />
      </View>

      <Toast
        message={error ?? ""}
        type="error"
        visible={!!error}
        onDismiss={() => setError(null)}
      />
    </KeyboardAvoidingView>
  );
}
