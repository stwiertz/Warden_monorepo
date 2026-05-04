import React from "react";
import { View, type ViewProps, type ViewStyle } from "react-native";
import { HUD } from "./tokens";

interface HudBracketProps extends ViewProps {
  /** Use dim white corners instead of accent */
  dim?: boolean;
  /** Override corner color */
  color?: string;
  /** Corner leg length in px (default 10) */
  size?: number;
}

/**
 * 4 corner brackets — 1px L-shaped legs at each corner of the wrapped box.
 * The signature decoration of the Tactical HUD direction.
 *
 * Mirrors `HudBracket` from docs/design/warden-mocks/screens/shared.jsx.
 */
export function HudBracket({
  dim = false,
  color,
  size = 10,
  children,
  style,
  ...rest
}: HudBracketProps) {
  const c = color ?? (dim ? HUD.whiteDim : HUD.accent);
  const leg = (extra: ViewStyle): ViewStyle => ({
    position: "absolute",
    width: size,
    height: size,
    borderColor: c,
    ...extra,
  });
  return (
    <View style={[{ position: "relative" }, style]} {...rest}>
      {children}
      <View pointerEvents="none" style={leg({ top: 0, left: 0, borderTopWidth: 1, borderLeftWidth: 1 })} />
      <View pointerEvents="none" style={leg({ top: 0, right: 0, borderTopWidth: 1, borderRightWidth: 1 })} />
      <View pointerEvents="none" style={leg({ bottom: 0, left: 0, borderBottomWidth: 1, borderLeftWidth: 1 })} />
      <View pointerEvents="none" style={leg({ bottom: 0, right: 0, borderBottomWidth: 1, borderRightWidth: 1 })} />
    </View>
  );
}
