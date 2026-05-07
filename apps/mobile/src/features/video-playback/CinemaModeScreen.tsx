import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import {
  HUD,
  HUD_FONT,
  Stamp,
  Icon,
  CircleBtn,
  MapArt,
  Reticle,
  Timeline,
} from "../../shared/components";

// Tactical HUD Cinema Mode — see docs/design/warden-mocks/screens/screens.jsx :: CinemaMode.
//
// VISUAL STUB — wire the controls + scrub head + minimap toggle to the real
// player when video-playback feature lands. The controls overlay is currently
// always visible; the design calls for tap-to-reveal + auto-hide after 4s.

interface CinemaModeProps {
  /** Episode title shown in the top overlay */
  title?: string;
  /** Episode metadata (e.g. "EP 04 · 13–9") */
  episodeMeta?: string;
  /** Session subtitle (e.g. "SCRIM · 24·04·26") */
  sessionMeta?: string;
  /** Current playback time, mm:ss */
  currentTime?: string;
  /** Total duration, mm:ss */
  totalTime?: string;
  /** Playback fraction 0..1 */
  progress?: number;
  /** Auto-detected scene marker positions */
  markers?: number[];
}

export function CinemaModeScreen({
  title = "SKYLINE",
  episodeMeta = "EP 04 · 13–9",
  sessionMeta = "SCRIM · 24·04·26",
  currentTime = "07:34",
  totalTime = "22:14",
  progress = 0.34,
  markers,
}: CinemaModeProps) {
  const [minimap, setMinimap] = useState(false);
  const [paused, setPaused] = useState(false);

  return (
    <View style={{ flex: 1, backgroundColor: HUD.bg }}>
      {/* Full-bleed video stand-in */}
      <MapArt seed={3} variant={minimap ? "minimap" : "pov"} />

      {/* Minimap center reticle */}
      {minimap && (
        <View
          pointerEvents="none"
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            marginLeft: -32,
            marginTop: -32,
          }}
        >
          <Reticle size={64} />
        </View>
      )}

      {/* Top vignette + overlay */}
      <LinearGradient
        colors={["rgba(0,0,0,0.55)", "rgba(0,0,0,0)"]}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "30%",
        }}
        pointerEvents="none"
      />
      <View
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          paddingHorizontal: 16,
          paddingTop: 12,
          flexDirection: "row",
          alignItems: "center",
          gap: 12,
        }}
      >
        <CircleBtn>
          <Icon.ChevLeft size={16} color={HUD.text} />
        </CircleBtn>
        <View style={{ flex: 1 }}>
          <Text
            style={{
              fontFamily: HUD_FONT.monoBold,
              fontSize: 12,
              letterSpacing: 1.5,
              color: HUD.text,
            }}
          >
            {title} <Text style={{ color: HUD.muted, marginLeft: 8 }}>{episodeMeta}</Text>
          </Text>
          <Stamp size={9}>{sessionMeta}</Stamp>
        </View>
        <CircleBtn label="MAPS">
          <Icon.Grid size={16} color={HUD.text} />
        </CircleBtn>
        <CircleBtn label="MINIMAP" active={minimap} onPress={() => setMinimap((m) => !m)}>
          <Icon.Map size={16} color={minimap ? HUD.accent : HUD.text} />
        </CircleBtn>
      </View>

      {/* Bottom vignette + controls */}
      <LinearGradient
        colors={["rgba(0,0,0,0)", "rgba(0,0,0,0.7)"]}
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "32%",
        }}
        pointerEvents="none"
      />
      <View
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          paddingHorizontal: 16,
          paddingBottom: 14,
          paddingTop: 12,
        }}
      >
        <Timeline progress={progress} markers={markers} />
        <View
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            marginTop: 6,
            marginBottom: 12,
          }}
        >
          <Stamp color={HUD.text}>{currentTime}</Stamp>
          <Stamp>{totalTime}</Stamp>
        </View>
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <View style={{ flexDirection: "row", gap: 8 }}>
            <CircleBtn>
              <Icon.Prev size={16} color={HUD.text} />
            </CircleBtn>
            <CircleBtn primary onPress={() => setPaused((p) => !p)}>
              {paused ? <Icon.Play size={18} color={HUD.bg} /> : <Icon.Pause size={18} color={HUD.bg} />}
            </CircleBtn>
            <CircleBtn>
              <Icon.Next size={16} color={HUD.text} />
            </CircleBtn>
          </View>
          <CircleBtn label="CLIP">
            <Icon.Scissors size={16} color={HUD.text} />
          </CircleBtn>
        </View>
      </View>
    </View>
  );
}
