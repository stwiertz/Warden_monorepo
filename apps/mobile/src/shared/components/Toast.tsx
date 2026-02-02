import React, { useEffect, useRef } from "react";
import { Animated, Text, View } from "react-native";

export type ToastType = "info" | "error" | "success";

interface ToastProps {
  message: string;
  type?: ToastType;
  visible: boolean;
  onDismiss: () => void;
  duration?: number;
}

const typeColors: Record<ToastType, string> = {
  info: "bg-surface",
  error: "bg-error",
  success: "bg-success",
};

export function Toast({
  message,
  type = "info",
  visible,
  onDismiss,
  duration = 3000,
}: ToastProps) {
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      Animated.timing(opacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }).start();

      const timer = setTimeout(() => {
        Animated.timing(opacity, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }).start(() => onDismiss());
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [visible, duration, onDismiss, opacity]);

  if (!visible) return null;

  return (
    <Animated.View
      style={{ opacity }}
      className="absolute bottom-12 left-4 right-4 z-50"
    >
      <View className={`${typeColors[type]} rounded-lg px-4 py-3`}>
        <Text className="text-text-primary text-body text-center">
          {message}
        </Text>
      </View>
    </Animated.View>
  );
}
