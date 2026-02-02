import React, { useEffect, useState, useRef } from "react";
import { View, Text } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../app/RootNavigator";
import { useVideoProcessing, getStageLabelFor } from "./useVideoProcessing";

type Props = NativeStackScreenProps<RootStackParamList, "Processing">;

const TIPS = [
  "Focus on one round at a time for better analysis",
  "Use voice comments to note key moments",
  "Review your positioning during crucial rounds",
  "Pay attention to economy decisions between rounds",
  "Compare your crosshair placement across maps",
  "Note utility usage patterns that worked well",
  "Look for patterns in how you lose rounds",
  "Track your first-kill vs first-death ratio",
  "Review post-plant positioning for improvements",
  "Analyze your rotation timing on CT side",
];

export function ProcessingScreen({ route, navigation }: Props) {
  const { sessionId } = route.params;
  const { progress, stage, status, error, startProcessing } =
    useVideoProcessing(sessionId);
  const [currentTip, setCurrentTip] = useState(0);
  const tipInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  // Start processing on mount
  useEffect(() => {
    startProcessing();
  }, [startProcessing]);

  // Rotate tips every 5-8 seconds
  useEffect(() => {
    tipInterval.current = setInterval(
      () => {
        setCurrentTip((prev) => (prev + 1) % TIPS.length);
      },
      5000 + Math.random() * 3000
    );
    return () => {
      if (tipInterval.current) clearInterval(tipInterval.current);
    };
  }, []);

  // Auto-navigate on completion
  useEffect(() => {
    if (status === "completed") {
      // Navigate to Card View (placeholder: go to Home for now since
      // Card View is Sprint 3). Pass sessionId for when it exists.
      navigation.replace("Home");
    }
  }, [status, navigation, sessionId]);

  return (
    <View className="flex-1 bg-background items-center justify-center px-8">
      <Text className="text-text-primary text-heading font-bold mb-2">
        Processing
      </Text>

      <Text className="text-text-secondary text-body mb-8">
        {getStageLabelFor(stage)}
      </Text>

      {/* Progress bar */}
      <View className="w-full h-3 bg-surface rounded-full mb-4 overflow-hidden">
        <View
          className="h-full rounded-full"
          style={{
            width: `${progress}%`,
            backgroundColor: "#FF6B00",
          }}
        />
      </View>

      <Text className="text-accent text-body font-semibold mb-12">
        {progress}%
      </Text>

      {/* Error state */}
      {status === "error" && (
        <View className="bg-surface rounded-xl p-4 mb-8 w-full">
          <Text className="text-error text-body text-center">
            {error ?? "An error occurred during processing."}
          </Text>
        </View>
      )}

      {/* Rotating tip */}
      <View className="bg-surface rounded-xl p-4 w-full">
        <Text className="text-text-secondary text-body text-center italic">
          {TIPS[currentTip]}
        </Text>
      </View>
    </View>
  );
}
