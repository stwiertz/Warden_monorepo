import React from "react";
import { View, Text } from "react-native";
import { Button } from "../../shared/components";

export function HomeScreen() {
  return (
    <View className="flex-1 bg-background items-center justify-center px-6">
      <Text className="text-text-primary text-heading font-bold mb-2">
        Warden
      </Text>
      <Text className="text-text-secondary text-body mb-8 text-center">
        Double XP for every training session
      </Text>
      <Button
        title="Import your first training session"
        onPress={() => {
          // TODO: Sprint 2 - Video Import
        }}
      />
    </View>
  );
}
