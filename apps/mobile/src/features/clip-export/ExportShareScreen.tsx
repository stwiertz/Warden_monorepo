import React from "react";
import { Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import {
  HUD,
  HUD_FONT,
  HudBracket,
  Stamp,
  Icon,
  MapArt,
} from "../../shared/components";

// Tactical HUD Export / Share — see docs/design/warden-mocks/screens/screens.jsx :: ExportShare.
//
// VISUAL STUB — when clip-export wiring lands, replace `progress`, `step`,
// and the share-target row state with the real export job state.

type StepState = "done" | "active" | "pending";

interface ExportShareProps {
  progress?: number; // 0..1
  step?: "trim" | "mux" | "encode" | "share";
  clipMeta?: string;
}

export function ExportShareScreen({
  progress = 0.74,
  step = "encode",
  clipMeta = "SKYLINE · 06:14 → 06:45 · 31s · MP4 720p",
}: ExportShareProps) {
  const pct = Math.round(progress * 100);
  const stepStates = stepStatesFor(step);

  return (
    <View style={{ flex: 1, backgroundColor: HUD.bg }}>
      {/* Top dimmed video preview */}
      <View style={{ height: "52%", overflow: "hidden" }}>
        <MapArt seed={3} variant="pov" />
        <LinearGradient
          colors={["rgba(10,10,13,0.4)", "rgba(10,10,13,1)"]}
          style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
        />
        <View
          style={{
            position: "absolute",
            top: 14,
            left: 16,
            flexDirection: "row",
            alignItems: "center",
            gap: 10,
          }}
        >
          <Icon.Scissors size={14} color={HUD.accent} />
          <Stamp color={HUD.accent}>EXPORTING CLIP</Stamp>
        </View>
      </View>

      {/* Bottom panel */}
      <View
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          paddingHorizontal: 20,
          paddingTop: 20,
          paddingBottom: 16,
        }}
      >
        <HudBracket
          style={{
            paddingHorizontal: 20,
            paddingTop: 20,
            paddingBottom: 16,
            backgroundColor: HUD.surface,
          }}
        >
          <View
            style={{
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "baseline",
              marginBottom: 4,
            }}
          >
            <Text
              style={{
                fontFamily: HUD_FONT.monoBold,
                fontSize: 14,
                letterSpacing: 2,
                color: HUD.text,
              }}
            >
              {step === "share" ? "READY TO SHARE" : "PREPARING CLIP"}
            </Text>
            <Text
              style={{
                fontFamily: HUD_FONT.monoMedium,
                fontSize: 12,
                color: HUD.accent,
              }}
            >
              {pct}
              <Text style={{ color: HUD.muted }}>%</Text>
            </Text>
          </View>
          <Stamp style={{ marginBottom: 14 }}>{clipMeta}</Stamp>

          {/* Progress bar */}
          <View
            style={{
              height: 6,
              backgroundColor: HUD.elev,
              position: "relative",
              marginBottom: 14,
            }}
          >
            <View
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                height: "100%",
                width: `${pct}%`,
                backgroundColor: HUD.accent,
                shadowColor: HUD.accent,
                shadowOpacity: 0.5,
                shadowRadius: 10,
                shadowOffset: { width: 0, height: 0 },
                elevation: 4,
              }}
            />
            {[0.25, 0.5, 0.75].map((p, i) => (
              <View
                key={i}
                style={{
                  position: "absolute",
                  top: -3,
                  left: `${p * 100}%`,
                  width: 1,
                  height: 12,
                  backgroundColor: HUD.dim,
                }}
              />
            ))}
          </View>

          {/* Step row */}
          <View style={{ flexDirection: "row", gap: 10, marginBottom: 16 }}>
            {(
              [
                { l: "TRIM", s: stepStates.trim },
                { l: "MUX VOICE", s: stepStates.mux },
                { l: "ENCODE", s: stepStates.encode },
                { l: "SHARE", s: stepStates.share },
              ] as { l: string; s: StepState }[]
            ).map((st) => (
              <View key={st.l} style={{ flex: 1, gap: 4 }}>
                <View
                  style={{
                    height: 2,
                    backgroundColor:
                      st.s === "done"
                        ? HUD.accent
                        : st.s === "active"
                        ? HUD.accentDim
                        : HUD.line,
                  }}
                />
                <Stamp
                  size={9}
                  color={st.s === "pending" ? HUD.dim : st.s === "active" ? HUD.accent : HUD.text}
                >
                  {st.l}
                </Stamp>
              </View>
            ))}
          </View>

          {/* Mock OS share targets */}
          <View
            style={{
              flexDirection: "row",
              gap: 10,
              opacity: step === "share" ? 1 : 0.5,
            }}
          >
            {["DISCORD", "WHATSAPP", "DRIVE", "COPY", "MORE"].map((n) => (
              <View key={n} style={{ flex: 1, alignItems: "center", gap: 4 }}>
                <View
                  style={{
                    width: 36,
                    height: 36,
                    borderWidth: 1,
                    borderColor: HUD.line,
                    backgroundColor: HUD.elev,
                  }}
                />
                <Stamp size={8}>{n}</Stamp>
              </View>
            ))}
          </View>
        </HudBracket>
      </View>
    </View>
  );
}

function stepStatesFor(active: "trim" | "mux" | "encode" | "share"): {
  trim: StepState;
  mux: StepState;
  encode: StepState;
  share: StepState;
} {
  const order: ("trim" | "mux" | "encode" | "share")[] = ["trim", "mux", "encode", "share"];
  const idx = order.indexOf(active);
  const stateFor = (i: number): StepState =>
    i < idx ? "done" : i === idx ? "active" : "pending";
  return {
    trim: stateFor(0),
    mux: stateFor(1),
    encode: stateFor(2),
    share: stateFor(3),
  };
}
