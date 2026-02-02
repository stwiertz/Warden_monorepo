import React, { useState, useCallback } from "react";
import { View, Text, Modal, Pressable } from "react-native";
import { useNavigation, useFocusEffect } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { Button } from "../../shared/components";
import { SessionList } from "../../features/session/SessionList";
import { useVideoImport } from "../../features/video-import/useVideoImport";
import {
  getAllSessions,
  deleteSession,
} from "../../features/session/sessionRepository";
import type { Session } from "../../shared/types";
import type { RootStackParamList } from "../RootNavigator";

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export function HomeScreen() {
  const navigation = useNavigation<NavigationProp>();
  const { importing, error, clearError, importVideo } = useVideoImport();
  const [sessions, setSessions] = useState<Session[]>([]);

  const loadSessions = useCallback(async () => {
    const data = await getAllSessions();
    setSessions(data);
  }, []);

  // Reload sessions every time the screen comes into focus
  useFocusEffect(
    useCallback(() => {
      loadSessions();
    }, [loadSessions])
  );

  const handleSessionPress = (session: Session) => {
    if (session.status === "processing") {
      navigation.navigate("Processing", { sessionId: session.id });
    }
    // "ready" sessions will navigate to Card View in Sprint 3
  };

  const handleDeleteSession = async (sessionId: string) => {
    await deleteSession(sessionId);
    await loadSessions();
  };

  const hasSessions = sessions.length > 0;
  const hasReadySession = sessions.some((s) => s.status === "ready");

  // Empty state
  if (!hasSessions) {
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
          onPress={importVideo}
          loading={importing}
        />
        <ErrorDialog error={error?.message ?? null} onDismiss={clearError} />
      </View>
    );
  }

  // Session list state
  return (
    <View className="flex-1 bg-background">
      {/* Header */}
      <View className="px-6 pt-14 pb-4">
        <Text className="text-text-primary text-heading font-bold">
          Warden
        </Text>
      </View>

      {/* Quick actions */}
      <View className="px-6 pb-4 gap-3">
        {hasReadySession && (
          <Button
            title="Resume last review"
            variant="secondary"
            onPress={() => {
              const ready = sessions.find((s) => s.status === "ready");
              if (ready) {
                // Will navigate to Card View in Sprint 3
              }
            }}
          />
        )}
        <Button
          title="Import new session"
          onPress={importVideo}
          loading={importing}
        />
      </View>

      {/* Session list */}
      <SessionList
        sessions={sessions}
        onSessionPress={handleSessionPress}
        onDeleteSession={handleDeleteSession}
      />

      <ErrorDialog error={error?.message ?? null} onDismiss={clearError} />
    </View>
  );
}

function ErrorDialog({
  error,
  onDismiss,
}: {
  error: string | null;
  onDismiss: () => void;
}) {
  if (!error) return null;

  return (
    <Modal transparent animationType="fade" visible={!!error}>
      <View className="flex-1 bg-black/60 items-center justify-center px-6">
        <View className="bg-surface rounded-2xl p-6 w-full max-w-sm">
          <Text className="text-text-primary text-body font-bold mb-2">
            Import Error
          </Text>
          <Text className="text-text-secondary text-body mb-6">{error}</Text>
          <Pressable
            onPress={onDismiss}
            className="bg-accent rounded-lg py-3 items-center"
          >
            <Text className="text-white font-semibold">OK</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}
