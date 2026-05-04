import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Alert,
} from "react-native";
import { Card } from "../../shared/components";
import type { Session } from "../../shared/types";

interface SessionListProps {
  sessions: Session[];
  onSessionPress: (session: Session) => void;
  onDeleteSession: (sessionId: string) => void;
}

const STATUS_COLORS: Record<Session["status"], string> = {
  importing: "#EAB308", // yellow
  processing: "#FF6B00", // accent/orange
  ready: "#22C55E", // green
  error: "#EF4444", // red
};

const STATUS_LABELS: Record<Session["status"], string> = {
  importing: "Importing",
  processing: "Processing",
  ready: "Ready",
  error: "Error",
};

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function SessionCard({
  session,
  onPress,
  onDelete,
}: {
  session: Session;
  onPress: () => void;
  onDelete: () => void;
}) {
  const handleLongPress = () => {
    Alert.alert(
      "Delete Session",
      `Delete "${session.name ?? "Untitled Session"}"? The video file will not be removed.`,
      [
        { text: "Cancel", style: "cancel" },
        { text: "Delete", style: "destructive", onPress: onDelete },
      ]
    );
  };

  return (
    <TouchableOpacity
      onPress={onPress}
      onLongPress={handleLongPress}
      activeOpacity={0.7}
    >
      <Card className="mb-3">
        <View className="flex-row items-center justify-between">
          <View className="flex-1 mr-3">
            <Text
              className="text-text-primary text-body font-semibold"
              numberOfLines={1}
            >
              {session.name ?? "Untitled Session"}
            </Text>
            <Text className="text-text-secondary text-sm mt-1">
              {formatDate(session.created_at)}
            </Text>
          </View>
          <View
            className="px-3 py-1 rounded-full"
            style={{ backgroundColor: STATUS_COLORS[session.status] + "20" }}
          >
            <Text
              className="text-sm font-medium"
              style={{ color: STATUS_COLORS[session.status] }}
            >
              {STATUS_LABELS[session.status]}
            </Text>
          </View>
        </View>
      </Card>
    </TouchableOpacity>
  );
}

export function SessionList({
  sessions,
  onSessionPress,
  onDeleteSession,
}: SessionListProps) {
  // Rendered inside HomeScreen's outer ScrollView, so we map plain Views
  // rather than nesting a FlatList (RN warns about that and virtualization
  // can't do useful work when the parent owns the scroll).
  return (
    <View style={{ paddingHorizontal: 16, paddingTop: 8 }}>
      {sessions.map((item) => (
        <SessionCard
          key={item.id}
          session={item}
          onPress={() => onSessionPress(item)}
          onDelete={() => onDeleteSession(item.id)}
        />
      ))}
    </View>
  );
}
