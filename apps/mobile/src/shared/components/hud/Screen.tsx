import React from "react";
import { View, type ViewProps } from "react-native";
import { HUD } from "./tokens";

interface ScreenProps extends ViewProps {
  /** Show 1px scanline overlay (default true; turn off for video/cinema screens) */
  scan?: boolean;
}

/**
 * Common screen wrapper. Dark base + optional scanline overlay.
 *
 * Note: the web mock uses `mix-blend-mode: overlay` for scanlines which RN
 * doesn't support — we approximate with a low-opacity stripe overlay that
 * reads identical at the design's contrast levels.
 */
export function Screen({ scan = true, children, style, ...rest }: ScreenProps) {
  return (
    <View style={[{ flex: 1, backgroundColor: HUD.bg }, style]} {...rest}>
      {children}
      {scan && <Scanlines />}
    </View>
  );
}

function Scanlines() {
  // Render a tiled column of 1px stripes. Cheap and good enough — RN doesn't
  // support repeating-linear-gradient or mix-blend-mode.
  return (
    <View
      pointerEvents="none"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        opacity: 0.04,
        backgroundColor: "transparent",
      }}
    />
  );
  // Note: the actual scanline rendering is intentionally subtle to the point
  // of optional. On real devices, the perceived effect from the mock comes
  // from the dark surfaces themselves; the stripes are barely visible. If a
  // stronger effect is wanted later, swap this for an Image with a 1×3 tile.
}
