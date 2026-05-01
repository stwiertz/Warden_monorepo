import React from "react";
import { Pressable, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import {
  HUD,
  HUD_FONT,
  HudBracket,
  Stamp,
  Icon,
  MapArt,
  Timeline,
  Waveform,
} from "../../shared/components";

// Tactical HUD Clip Creation — see docs/design/warden-mocks/screens/screens.jsx :: ClipMode.
//
// VISUAL STUB — clip-export feature isn't implemented yet. When it lands, wire:
// - clip handle drag → update clip.start/end
// - voice slot tap → start/stop record + waveform from real audio
// - EXPORT → ExportShareScreen with the rendered clip job

interface ClipModeProps {
  episodeTitle?: string;
  clipDurationLabel?: string;
  clipRange?: string;
  clip?: { start: number; end: number };
  progress?: number;
  startTime?: string;
  endTime?: string;
}

type SlotState = "empty" | "recorded" | "recording";

export function ClipModeScreen({
  episodeTitle = "SKYLINE · EP 04",
  clipDurationLabel = "CLIP · 00:31",
  clipRange = "CLIP 06:14 → 06:45",
  clip = { start: 0.28, end: 0.42 },
  progress = 0.34,
  startTime = "06:14",
  endTime = "22:14",
}: ClipModeProps) {
  return (
    <View style={{ flex: 1, backgroundColor: HUD.bg }}>
      <MapArt seed={3} variant="pov" />
      <View
        pointerEvents="none"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(10,10,13,0.42)",
        }}
      />

      {/* Top strip */}
      <View
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          paddingHorizontal: 16,
          paddingTop: 10,
          flexDirection: "row",
          alignItems: "center",
          gap: 10,
        }}
      >
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 8,
            paddingHorizontal: 10,
            paddingVertical: 4,
            borderWidth: 1,
            borderColor: HUD.accent,
            backgroundColor: "rgba(255,107,0,0.08)",
          }}
        >
          <Icon.Scissors size={12} color={HUD.accent} />
          <Stamp color={HUD.accent}>{clipDurationLabel}</Stamp>
        </View>
        <Stamp>{episodeTitle}</Stamp>
        <View style={{ flex: 1 }} />
        <Pressable
          style={({ pressed }) => ({
            paddingHorizontal: 14,
            paddingVertical: 6,
            backgroundColor: HUD.accent,
            opacity: pressed ? 0.7 : 1,
            shadowColor: HUD.accent,
            shadowOpacity: 0.35,
            shadowRadius: 12,
            shadowOffset: { width: 0, height: 0 },
            elevation: 4,
          })}
        >
          <Text
            style={{
              fontFamily: HUD_FONT.monoBold,
              fontSize: 11,
              letterSpacing: 1.5,
              color: HUD.bg,
            }}
          >
            EXPORT ›
          </Text>
        </Pressable>
      </View>

      {/* Bottom panel */}
      <LinearGradient
        colors={["rgba(10,10,13,0)", "rgba(10,10,13,0.95)"]}
        locations={[0, 0.6]}
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          paddingTop: 28,
        }}
      >
        <View style={{ paddingHorizontal: 16, paddingBottom: 12 }}>
          <Timeline progress={progress} clip={clip} />
          <View
            style={{
              flexDirection: "row",
              justifyContent: "space-between",
              marginTop: 6,
            }}
          >
            <Stamp>{startTime}</Stamp>
            <Stamp color={HUD.accent}>{clipRange}</Stamp>
            <Stamp>{endTime}</Stamp>
          </View>
        </View>

        <HudBracket
          dim
          style={{
            marginHorizontal: 16,
            marginBottom: 14,
            padding: 14,
            backgroundColor: HUD.surface,
          }}
        >
          <View
            style={{
              flexDirection: "row",
              justifyContent: "space-between",
              marginBottom: 10,
            }}
          >
            <Stamp color={HUD.text}>VOICE COMMENTARY</Stamp>
            <Stamp>3 SLOTS</Stamp>
          </View>
          <View style={{ flexDirection: "row", gap: 8 }}>
            <VoiceSlot label="BEFORE" state="recorded" duration="0:08" seed={1} />
            <VoiceSlot label="ON CLIP" state="recording" duration="0:04" seed={2} />
            <VoiceSlot label="AFTER" state="empty" />
          </View>
        </HudBracket>
      </LinearGradient>
    </View>
  );
}

function VoiceSlot({
  label,
  state,
  duration,
  seed = 1,
}: {
  label: string;
  state: SlotState;
  duration?: string;
  seed?: number;
}) {
  const isRec = state === "recording";
  const isEmpty = state === "empty";
  return (
    <View
      style={{
        flex: 1,
        padding: 12,
        borderWidth: 1,
        borderColor: isRec ? HUD.accent : HUD.line,
        backgroundColor: isRec ? "rgba(255,107,0,0.06)" : isEmpty ? "transparent" : HUD.elev,
        minHeight: 56,
      }}
    >
      <View
        style={{
          flexDirection: "row",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          {isRec && (
            <View
              style={{
                width: 6,
                height: 6,
                borderRadius: 3,
                backgroundColor: HUD.accent,
              }}
            />
          )}
          <Stamp color={isRec ? HUD.accent : isEmpty ? HUD.dim : HUD.text}>{label}</Stamp>
        </View>
        {duration && (
          <Text
            style={{
              fontFamily: HUD_FONT.monoRegular,
              fontSize: 10,
              color: isRec ? HUD.accent : HUD.muted,
              letterSpacing: 0.5,
            }}
          >
            {duration}
          </Text>
        )}
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        {isEmpty ? (
          <>
            <View
              style={{
                width: 26,
                height: 26,
                borderWidth: 1,
                borderColor: HUD.line,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon.Mic size={13} color={HUD.muted} />
            </View>
            <Stamp>TAP TO RECORD</Stamp>
          </>
        ) : isRec ? (
          <>
            <View
              style={{
                width: 26,
                height: 26,
                backgroundColor: HUD.accent,
                alignItems: "center",
                justifyContent: "center",
                shadowColor: HUD.accent,
                shadowOpacity: 0.6,
                shadowRadius: 10,
                shadowOffset: { width: 0, height: 0 },
                elevation: 4,
              }}
            >
              <Icon.Stop size={11} color={HUD.bg} />
            </View>
            <Waveform seed={seed} bars={18} color={HUD.accent} height={16} />
          </>
        ) : (
          <>
            <View
              style={{
                width: 26,
                height: 26,
                borderWidth: 1,
                borderColor: HUD.line,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon.Play size={11} color={HUD.text} />
            </View>
            <Waveform seed={seed} bars={18} color={HUD.muted} height={16} />
          </>
        )}
      </View>
    </View>
  );
}
