import React, { useCallback, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  HUD,
  HUD_FONT,
  HudBracket,
  Stamp,
  WardenMark,
  Icon,
  EngageButton,
} from "../../shared/components";
import { SessionList } from "../../features/session/SessionList";
import { useVideoImport } from "../../features/video-import/useVideoImport";
import {
  deleteSession,
  getAllSessions,
} from "../../features/session/sessionRepository";
import type { Session } from "../../shared/types";
import type { RootStackParamList } from "../RootNavigator";

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

// Tactical HUD ColdStart — see docs/design/warden-mocks/screens/screens.jsx :: ColdStart.
// Two paths: Resume Last Review (when there's a ready session) and Import New Video.
// When more than one session exists, the rest stack as a tactical session list below.

export function HomeScreen() {
  const navigation = useNavigation<NavigationProp>();
  const { width, height } = useWindowDimensions();
  const isLandscape = width > height;
  const insets = useSafeAreaInsets();
  const { importing, error, clearError, importVideo } = useVideoImport();
  const [sessions, setSessions] = useState<Session[]>([]);

  const loadSessions = useCallback(async () => {
    setSessions(await getAllSessions());
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadSessions();
    }, [loadSessions])
  );

  const lastReady = sessions.find((s) => s.status === "ready");
  const handleResume = () => {
    // Card View lands in Sprint 3; until then we stay on Home and surface
    // a friendly stamp in the resume card.
  };

  const handleImport = () => {
    importVideo();
  };

  const handleSessionPress = (session: Session) => {
    if (session.status === "processing") {
      navigation.navigate("Processing", { sessionId: session.id });
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    await deleteSession(sessionId);
    await loadSessions();
  };

  const totalSessions = sessions.length;
  const readySessions = sessions.filter((s) => s.status === "ready").length;

  return (
    <View style={{ flex: 1, backgroundColor: HUD.bg }}>
      <ScrollView
        contentContainerStyle={{
          flexGrow: 1,
          paddingBottom: 56 + insets.bottom,
        }}
      >
        {/* Top brand strip */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "space-between",
            paddingHorizontal: 20,
            paddingTop: 18 + insets.top,
            paddingBottom: 4,
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <WardenMark size={20} />
            <View>
              <Text
                style={{
                  fontFamily: HUD_FONT.monoBold,
                  fontSize: 12,
                  letterSpacing: 2,
                  color: HUD.text,
                }}
              >
                WARDEN
              </Text>
              <Stamp size={9}>MATCH ANALYSIS · v0.4.1</Stamp>
            </View>
          </View>
          <Stamp size={9}>SES · {todayStamp()}</Stamp>
        </View>

        {/* Two-card hero */}
        <View
          style={{
            flexDirection: isLandscape ? "row" : "column",
            gap: isLandscape ? 16 : 12,
            paddingHorizontal: 16,
            paddingTop: 24,
          }}
        >
          <ColdCard
            kind="resume"
            primary
            disabled={!lastReady}
            onPress={lastReady ? handleResume : handleImport}
            title={lastReady ? "RESUME LAST REVIEW" : "NO SESSIONS YET"}
            subtitle={lastReady ? formatSessionSubtitle(lastReady) : "GET STARTED"}
            meta={
              lastReady
                ? [
                    sessionLine(lastReady),
                    `Last opened ${relativeTime(lastReady.updated_at)}`,
                  ]
                : ["Import a session below to begin"]
            }
            episodeCount={lastReady ? 8 : 0}
            portrait={!isLandscape}
          />

          <ColdCard
            kind="import"
            primary={!lastReady}
            onPress={handleImport}
            title="IMPORT NEW VIDEO"
            subtitle="MP4 · MOV · MKV"
            meta={[
              "Auto-detect map breaks",
              "Up to 4h source",
              "Black-frame slicing",
            ]}
            portrait={!isLandscape}
            loading={importing}
          />
        </View>

        {/* Existing sessions list — slim tactical version */}
        {sessions.length > 0 && (
          <View style={{ marginTop: 28, paddingHorizontal: 20 }}>
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                paddingBottom: 8,
                borderBottomWidth: 1,
                borderBottomColor: HUD.line,
                marginBottom: 8,
              }}
            >
              <Stamp color={HUD.text}>ALL SESSIONS</Stamp>
              <Stamp>{totalSessions} TOTAL</Stamp>
            </View>
            <SessionList
              sessions={sessions}
              onSessionPress={handleSessionPress}
              onDeleteSession={handleDeleteSession}
            />
          </View>
        )}
      </ScrollView>

      {/* Bottom tactical strip */}
      <View
        style={{
          position: "absolute",
          left: 20,
          right: 20,
          bottom: 12 + insets.bottom,
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          paddingTop: 10,
          borderTopWidth: 1,
          borderTopColor: HUD.line,
        }}
      >
        <Stamp>
          {totalSessions} SESSION{totalSessions === 1 ? "" : "S"} ON DEVICE
        </Stamp>
        <Stamp color={readySessions > 0 ? HUD.accent : HUD.muted}>
          {readySessions > 0 ? "● READY" : "○ EMPTY"}
        </Stamp>
      </View>

      <ErrorDialog error={error?.message ?? null} onDismiss={clearError} />
    </View>
  );
}

// ─── ColdCard ─────────────────────────────────────────────────────────────

interface ColdCardProps {
  kind: "resume" | "import";
  primary?: boolean;
  disabled?: boolean;
  loading?: boolean;
  onPress: () => void;
  title: string;
  subtitle: string;
  meta: string[];
  episodeCount?: number;
  portrait: boolean;
}

function ColdCard({
  kind,
  primary = false,
  disabled = false,
  loading = false,
  onPress,
  title,
  subtitle,
  meta,
  episodeCount = 0,
  portrait,
}: ColdCardProps) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => ({
        flex: 1,
        opacity: pressed || disabled ? 0.65 : 1,
      })}
    >
      <HudBracket
        dim={!primary}
        style={{
          padding: portrait ? 18 : 22,
          backgroundColor: primary ? "rgba(255,107,0,0.05)" : HUD.surface,
          minHeight: portrait ? 200 : 240,
        }}
      >
        <View
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <Stamp color={primary ? HUD.accent : HUD.dim}>
            {primary ? "▸ RESUME" : "▸ IMPORT"}
          </Stamp>
          <Stamp>{subtitle}</Stamp>
        </View>

        <View
          style={{
            flex: 1,
            alignItems: "center",
            justifyContent: "center",
            paddingVertical: 24,
            minHeight: portrait ? 80 : 100,
          }}
        >
          {kind === "resume" ? (
            <ResumePreview episodes={episodeCount} portrait={portrait} />
          ) : (
            <ImportPreview />
          )}
        </View>

        <Text
          style={{
            fontFamily: HUD_FONT.monoBold,
            letterSpacing: 1.5,
            fontSize: portrait ? 15 : 17,
            color: HUD.text,
            marginBottom: 6,
          }}
        >
          {loading ? "STARTING…" : title}
        </Text>

        <View style={{ gap: 3 }}>
          {meta.map((m) => (
            <View key={m} style={{ flexDirection: "row" }}>
              <Text style={{ color: HUD.dim, marginRight: 6, fontFamily: HUD_FONT.sansRegular }}>
                ›
              </Text>
              <Text
                style={{
                  fontSize: 11,
                  color: HUD.muted,
                  fontFamily: HUD_FONT.sansRegular,
                  flexShrink: 1,
                }}
              >
                {m}
              </Text>
            </View>
          ))}
        </View>
      </HudBracket>
    </Pressable>
  );
}

function ResumePreview({ episodes, portrait }: { episodes: number; portrait: boolean }) {
  if (episodes <= 0) {
    return (
      <Stamp color={HUD.dim} size={11}>
        NO RECENT SESSION
      </Stamp>
    );
  }
  const slabs = Math.min(8, episodes);
  const active = Math.min(3, slabs - 1);
  return (
    <View style={{ width: "100%", maxWidth: 220, gap: 6 }}>
      <View style={{ flexDirection: "row", gap: 2, height: 28, alignItems: "flex-end" }}>
        {Array.from({ length: slabs }).map((_, i) => {
          const isActive = i === active;
          const isPast = i < active;
          return (
            <View
              key={i}
              style={{
                flex: 1,
                height: 22 + (isActive ? 6 : 0),
                backgroundColor: isActive
                  ? HUD.accent
                  : isPast
                  ? "rgba(255,107,0,0.25)"
                  : HUD.elev2,
                borderRadius: 1,
              }}
            />
          );
        })}
      </View>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Stamp size={9} color={HUD.dim}>
          EP 01
        </Stamp>
        <Stamp size={9} color={HUD.dim}>
          · · ·
        </Stamp>
        <Stamp size={9} color={HUD.dim}>
          EP {String(slabs).padStart(2, "0")}
        </Stamp>
      </View>
    </View>
  );
}

function ImportPreview() {
  return (
    <View style={{ alignItems: "center", gap: 8 }}>
      <HudBracket
        dim
        style={{
          width: 56,
          height: 56,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon.Plus size={22} color={HUD.muted} />
      </HudBracket>
      <Stamp>DROP OR BROWSE</Stamp>
    </View>
  );
}

// ─── helpers ──────────────────────────────────────────────────────────────

function todayStamp(): string {
  const d = new Date();
  return [
    String(d.getFullYear()).slice(-2),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("·");
}

function formatSessionSubtitle(s: Session): string {
  const d = new Date(s.created_at);
  return [
    "SCRIM",
    [
      String(d.getFullYear()).slice(-2),
      String(d.getMonth() + 1).padStart(2, "0"),
      String(d.getDate()).padStart(2, "0"),
    ].join("·"),
  ].join(" · ");
}

function sessionLine(s: Session): string {
  const name = s.name?.trim();
  return name ? `${name}` : "Untitled session";
}

function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

// ─── error dialog (kept tactical) ────────────────────────────────────────

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
      <View
        style={{
          flex: 1,
          backgroundColor: "rgba(0,0,0,0.6)",
          alignItems: "center",
          justifyContent: "center",
          paddingHorizontal: 20,
        }}
      >
        <HudBracket
          style={{
            width: "100%",
            maxWidth: 360,
            padding: 22,
            backgroundColor: HUD.surface,
          }}
        >
          <Stamp color={HUD.accent} style={{ marginBottom: 8 }}>
            ▸ IMPORT ERROR
          </Stamp>
          <Text
            style={{
              fontFamily: HUD_FONT.sansRegular,
              fontSize: 14,
              color: HUD.text,
              lineHeight: 20,
              marginBottom: 18,
            }}
          >
            {error}
          </Text>
          <EngageButton label="ACK" onPress={onDismiss} />
        </HudBracket>
      </View>
    </Modal>
  );
}
