import React, { useEffect, useRef, useState } from "react";
import { Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../app/RootNavigator";
import {
  HUD,
  HUD_FONT,
  HudBracket,
  Stamp,
  WardenMark,
  RadarRing,
} from "../../shared/components";
import { useVideoProcessing, getStageLabelFor } from "./useVideoProcessing";

type Props = NativeStackScreenProps<RootStackParamList, "Processing">;

const TIPS = [
  "Double-tap the top-left of any clip to flip to minimap.",
  "Drag the clip handles to adjust your clip boundaries.",
  "Add voice before, during, or after your clip.",
  "Sort maps by closest score to find the most important rounds.",
  "Your review progress is saved automatically — pick up where you left off.",
];

// Tactical HUD radar — see docs/design/warden-mocks/screens/screens.jsx :: Processing.

export function ProcessingScreen({ route, navigation }: Props) {
  const { sessionId } = route.params;
  const { progress, stage, status, error, startProcessing } = useVideoProcessing(sessionId);
  const [currentTip, setCurrentTip] = useState(0);
  const tipInterval = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    startProcessing();
  }, [startProcessing]);

  useEffect(() => {
    tipInterval.current = setInterval(
      () => setCurrentTip((p) => (p + 1) % TIPS.length),
      5500
    );
    return () => {
      if (tipInterval.current) clearInterval(tipInterval.current);
    };
  }, []);

  useEffect(() => {
    if (status === "completed") {
      navigation.replace("Home");
    }
  }, [status, navigation, sessionId]);

  const fraction = Math.max(0, Math.min(1, progress / 100));
  const isError = status === "error";

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: HUD.bg,
        paddingHorizontal: 20,
        paddingVertical: 16,
      }}
    >
      {/* Header */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          <WardenMark size={18} />
          <Stamp size={11} color={HUD.text}>
            WARDEN · ANALYZING
          </Stamp>
        </View>
        <Stamp color={isError ? "#EF4444" : HUD.accent}>
          {isError ? "● ERROR" : "● ENCODING"}
        </Stamp>
      </View>

      {/* Center radar + stats */}
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 36,
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          <View style={{ position: "relative", width: 140, height: 140 }}>
            <RadarRing size={140} progress={fraction} />
            <View
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Text
                style={{
                  fontFamily: HUD_FONT.monoBold,
                  fontSize: 26,
                  letterSpacing: 1,
                  color: HUD.text,
                }}
              >
                {progress}
                <Text style={{ fontSize: 14, color: HUD.muted }}>%</Text>
              </Text>
              <Stamp size={9} style={{ marginTop: 2 }}>
                {getStageLabelFor(stage).toUpperCase()}
              </Stamp>
            </View>
          </View>

          <View style={{ minWidth: 220, gap: 12 }}>
            <Stat label="SESSION" value={shortId(sessionId)} />
            <Stat label="STAGE" value={getStageLabelFor(stage)} accent />
            <Stat label="PROGRESS" value={`${progress}%`} />
            <Stat
              label="STATUS"
              value={isError ? "ERROR" : status?.toUpperCase() ?? "—"}
              accent={!isError}
            />
          </View>
        </View>

        {isError && error && (
          <HudBracket
            dim
            style={{
              marginTop: 24,
              padding: 14,
              backgroundColor: HUD.surface,
              maxWidth: 480,
            }}
          >
            <Stamp color="#EF4444" style={{ marginBottom: 6 }}>
              ▸ FAULT
            </Stamp>
            <Text
              style={{
                fontFamily: HUD_FONT.sansRegular,
                fontSize: 13,
                color: HUD.text,
              }}
            >
              {error}
            </Text>
          </HudBracket>
        )}
      </View>

      {/* Tip banner */}
      <HudBracket
        dim
        style={{
          padding: 14,
          backgroundColor: HUD.surface,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
          <Stamp color={HUD.accent}>
            TIP {String(currentTip + 1).padStart(2, "0")} · {String(TIPS.length).padStart(2, "0")}
          </Stamp>
          <View style={{ width: 1, height: 14, backgroundColor: HUD.line }} />
          <Text
            style={{
              flex: 1,
              fontFamily: HUD_FONT.sansRegular,
              fontSize: 13,
              color: HUD.text,
            }}
          >
            {TIPS[currentTip]}
          </Text>
          <View style={{ flexDirection: "row", gap: 4 }}>
            {TIPS.map((_, i) => (
              <View
                key={i}
                style={{
                  width: 18,
                  height: 2,
                  backgroundColor: i === currentTip ? HUD.accent : HUD.line,
                }}
              />
            ))}
          </View>
        </View>
      </HudBracket>
    </View>
  );
}

function Stat({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <View
      style={{
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "baseline",
        borderBottomWidth: 1,
        borderBottomColor: HUD.line,
        paddingBottom: 6,
      }}
    >
      <Stamp>{label}</Stamp>
      <Text
        style={{
          fontFamily: HUD_FONT.monoMedium,
          fontSize: 13,
          color: accent ? HUD.accent : HUD.text,
          letterSpacing: 0.3,
        }}
      >
        {value}
      </Text>
    </View>
  );
}

function shortId(id: string): string {
  return id.slice(0, 8).toUpperCase();
}
