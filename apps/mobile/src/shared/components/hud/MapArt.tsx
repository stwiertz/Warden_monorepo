import React from "react";
import { View } from "react-native";
import Svg, { Defs, Line, Path, Pattern, Rect } from "react-native-svg";
import { HUD } from "./tokens";

interface MapArtProps {
  /** "pov" = first-person crosshair vibe; "minimap" = top-down recon */
  variant?: "pov" | "minimap";
  /** Deterministic seed for player-dot placement */
  seed?: number;
}

/**
 * Tactical map placeholder — abstract grid + simulated geometry blocks +
 * crosshair (POV) or player dots (minimap). Used as a stand-in for real
 * video / minimap rendering. Replace with the actual video surface when
 * playback lands.
 */
export function MapArt({ variant = "pov", seed = 1 }: MapArtProps) {
  const rand = (n: number) => {
    const x = Math.sin(seed * 9999 + n) * 10000;
    return x - Math.floor(x);
  };
  const dots = Array.from({ length: 6 }, (_, i) => ({
    x: 12 + rand(i) * 76,
    y: 18 + rand(i + 10) * 64,
    team: i < 3 ? "o" : "b",
  }));

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: variant === "minimap" ? "#0d0f15" : "#0f0d12",
        overflow: "hidden",
      }}
    >
      {/* grid */}
      <Svg
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, opacity: variant === "minimap" ? 0.35 : 0.18 }}
        width="100%"
        height="100%"
      >
        <Defs>
          <Pattern id={`grid-${seed}`} width={24} height={24} patternUnits="userSpaceOnUse">
            <Path d="M 24 0 L 0 0 0 24" fill="none" stroke="#3a3a44" strokeWidth={0.5} />
          </Pattern>
        </Defs>
        <Rect width="100%" height="100%" fill={`url(#grid-${seed})`} />
      </Svg>

      {/* simulated geometry blocks */}
      <Svg
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        width="100%"
        height="100%"
      >
        <Rect x={20} y={30} width={20} height={14} fill="#1f1f28" stroke="#2a2a34" strokeWidth={0.3} />
        <Rect x={50} y={20} width={16} height={22} fill="#1f1f28" stroke="#2a2a34" strokeWidth={0.3} />
        <Rect x={35} y={60} width={28} height={12} fill="#1f1f28" stroke="#2a2a34" strokeWidth={0.3} />
        <Rect x={68} y={55} width={18} height={20} fill="#1f1f28" stroke="#2a2a34" strokeWidth={0.3} />
        <Line x1={0} y1={50} x2={100} y2={50} stroke="#2a2a34" strokeWidth={0.3} strokeDasharray="2 2" />
        <Line x1={50} y1={0} x2={50} y2={100} stroke="#2a2a34" strokeWidth={0.3} strokeDasharray="2 2" />
      </Svg>

      {/* player dots (minimap only) */}
      {variant === "minimap" &&
        dots.map((d, i) => (
          <View
            key={i}
            style={{
              position: "absolute",
              left: `${d.x}%`,
              top: `${d.y}%`,
              width: 8,
              height: 8,
              borderRadius: 2,
              backgroundColor: d.team === "o" ? HUD.accent : HUD.teamBlue,
              transform: [{ translateX: -4 }, { translateY: -4 }],
              shadowColor: d.team === "o" ? HUD.accent : HUD.teamBlue,
              shadowOpacity: 0.6,
              shadowRadius: 8,
              shadowOffset: { width: 0, height: 0 },
              elevation: 4,
            }}
          />
        ))}

      {/* POV center crosshair */}
      {variant === "pov" && (
        <View
          pointerEvents="none"
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: 24,
            height: 24,
            marginLeft: -12,
            marginTop: -12,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
            <Line x1={12} y1={2} x2={12} y2={8} stroke="rgba(240,240,240,0.35)" strokeWidth={1} />
            <Line x1={12} y1={16} x2={12} y2={22} stroke="rgba(240,240,240,0.35)" strokeWidth={1} />
            <Line x1={2} y1={12} x2={8} y2={12} stroke="rgba(240,240,240,0.35)" strokeWidth={1} />
            <Line x1={16} y1={12} x2={22} y2={12} stroke="rgba(240,240,240,0.35)" strokeWidth={1} />
          </Svg>
        </View>
      )}
    </View>
  );
}
