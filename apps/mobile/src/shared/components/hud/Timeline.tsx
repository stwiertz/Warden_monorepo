import React from "react";
import { View } from "react-native";
import { HUD } from "./tokens";
import { ClipHandle } from "./Marks";

interface TimelineProps {
  /** Playback head position, 0..1 */
  progress?: number;
  /** Optional clip region overlay */
  clip?: { start: number; end: number };
  /** Auto-detected scene marker positions, 0..1 each */
  markers?: number[];
}

/**
 * 22px-tall timeline strip — used in cinema mode + clip mode.
 * Composition: dim base track, white-60% progress fill, dim scene markers,
 * optional clip region with reticle-style L-bracket handles, and a 2px
 * accent scrub head.
 */
export function Timeline({
  progress = 0,
  clip,
  markers = [0.18, 0.35, 0.52, 0.7, 0.86],
}: TimelineProps) {
  const clamped = Math.max(0, Math.min(1, progress));
  return (
    <View style={{ position: "relative", height: 22, width: "100%" }}>
      {/* base track */}
      <View
        style={{
          position: "absolute",
          top: 9,
          left: 0,
          right: 0,
          height: 4,
          backgroundColor: HUD.elev,
          borderRadius: 1,
        }}
      >
        <View
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            height: "100%",
            width: `${clamped * 100}%`,
            backgroundColor: "rgba(255,255,255,0.6)",
            borderRadius: 1,
          }}
        />
      </View>

      {/* scene markers */}
      {markers.map((p, i) => (
        <View
          key={i}
          style={{
            position: "absolute",
            top: 5,
            left: `${p * 100}%`,
            width: 1,
            height: 12,
            backgroundColor: HUD.dim,
            transform: [{ translateX: -0.5 }],
          }}
        />
      ))}

      {/* clip region */}
      {clip && (
        <>
          <View
            style={{
              position: "absolute",
              top: 4,
              left: `${clip.start * 100}%`,
              width: `${(clip.end - clip.start) * 100}%`,
              height: 14,
              backgroundColor: HUD.accentSoft,
              borderWidth: 1,
              borderColor: HUD.accent,
              shadowColor: HUD.accent,
              shadowOpacity: 0.4,
              shadowRadius: 12,
              shadowOffset: { width: 0, height: 0 },
              elevation: 4,
            }}
          />
          <View style={{ position: "absolute", top: -2, left: `${clip.start * 100}%`, transform: [{ translateX: -7 }] }}>
            <ClipHandle dir="start" />
          </View>
          <View style={{ position: "absolute", top: -2, left: `${clip.end * 100}%`, transform: [{ translateX: -7 }] }}>
            <ClipHandle dir="end" />
          </View>
        </>
      )}

      {/* scrub head */}
      <View
        style={{
          position: "absolute",
          top: 0,
          left: `${clamped * 100}%`,
          transform: [{ translateX: -1 }],
          width: 2,
          height: 22,
          backgroundColor: HUD.accent,
          borderRadius: 1,
          shadowColor: HUD.accent,
          shadowOpacity: 0.6,
          shadowRadius: 8,
          shadowOffset: { width: 0, height: 0 },
          elevation: 4,
        }}
      />
    </View>
  );
}
