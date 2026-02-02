import React from "react";
import { ActivityIndicator, View, Text } from "react-native";

interface LoadingSpinnerProps {
  message?: string;
}

export function LoadingSpinner({ message }: LoadingSpinnerProps) {
  return (
    <View className="flex-1 bg-background items-center justify-center">
      <ActivityIndicator size="large" color="#FF6B00" />
      {message && (
        <Text className="text-text-secondary text-body mt-4">{message}</Text>
      )}
    </View>
  );
}
