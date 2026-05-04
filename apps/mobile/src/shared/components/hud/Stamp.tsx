import React from "react";
import { Text, type TextProps } from "react-native";
import { HUD, HUD_FONT } from "./tokens";

interface StampProps extends TextProps {
  /** Override color (default: muted) */
  color?: string;
  /** Override font size (default: 10) */
  size?: number;
  /** Override letter-spacing (default: 1) */
  spacing?: number;
}

/**
 * Tactical mono label — small, ALL CAPS, tracked. Used for every "stamp" in
 * the design: ACCESS / OP-XX / READY / EP04 / etc.
 *
 * Mirrors `Stamp` from docs/design/warden-mocks/screens/screens.jsx.
 */
export function Stamp({ children, color, size = 10, spacing = 1, style, ...rest }: StampProps) {
  return (
    <Text
      {...rest}
      style={[
        {
          fontFamily: HUD_FONT.monoRegular,
          fontSize: size,
          letterSpacing: spacing,
          color: color ?? HUD.muted,
          textTransform: "uppercase",
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}
