import React from "react";
import { View } from "react-native";
import { HUD } from "./tokens";

type CornerTickPos = "tl" | "tr" | "bl" | "br";

interface CornerTickProps {
  pos: CornerTickPos;
  /** Inset from the closest edge in px (default 10) */
  inset?: number;
  /** Leg length in px (default 14) */
  size?: number;
  /** Top-corner extra padding (e.g. for the status bar / notch safe area) */
  topOffset?: number;
  /** Bottom-corner extra padding (e.g. for a status strip below) */
  bottomOffset?: number;
}

/**
 * Decorative L crosshair in a corner. Used at the four corners of full-screen
 * surfaces (login). Pure decoration — no interactivity.
 */
export function CornerTick({ pos, inset = 10, size = 14, topOffset = 0, bottomOffset = 0 }: CornerTickProps) {
  const base = { position: "absolute" as const, width: size, height: size };
  const color = HUD.whiteDim;
  switch (pos) {
    case "tl":
      return (
        <View style={[base, { top: inset + topOffset, left: inset, borderTopWidth: 1, borderLeftWidth: 1, borderColor: color }]} />
      );
    case "tr":
      return (
        <View style={[base, { top: inset + topOffset, right: inset, borderTopWidth: 1, borderRightWidth: 1, borderColor: color }]} />
      );
    case "bl":
      return (
        <View
          style={[
            base,
            { bottom: inset + bottomOffset, left: inset, borderBottomWidth: 1, borderLeftWidth: 1, borderColor: color },
          ]}
        />
      );
    case "br":
      return (
        <View
          style={[
            base,
            { bottom: inset + bottomOffset, right: inset, borderBottomWidth: 1, borderRightWidth: 1, borderColor: color },
          ]}
        />
      );
  }
}
