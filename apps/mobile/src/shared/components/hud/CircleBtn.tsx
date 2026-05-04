import React from "react";
import { Pressable, View, type PressableProps } from "react-native";
import { HUD } from "./tokens";
import { Stamp } from "./Stamp";

interface CircleBtnProps extends Omit<PressableProps, "children"> {
  /** 44 × 44 pixel-rounded primary button (accent fill) */
  primary?: boolean;
  /** Active state (e.g., minimap toggle on) — accent border + glow */
  active?: boolean;
  /** Optional small mono label below the button */
  label?: string;
  children: React.ReactNode;
}

/**
 * 44×44 cinema-overlay control. Three states:
 *   - default: dark surface + subtle white border
 *   - active:  accent-soft fill + accent border + accent glow
 *   - primary: accent fill (used for play/pause)
 */
export function CircleBtn({
  primary = false,
  active = false,
  label,
  children,
  disabled,
  ...rest
}: CircleBtnProps) {
  return (
    <View style={{ alignItems: "center", gap: 3 }}>
      <Pressable
        {...rest}
        disabled={disabled}
        style={({ pressed }) => ({
          width: 44,
          height: 44,
          borderRadius: primary ? 22 : 6,
          backgroundColor: primary
            ? HUD.accent
            : active
            ? HUD.accentSoft
            : "rgba(20,20,26,0.7)",
          borderWidth: primary ? 0 : 1,
          borderColor: active ? HUD.accent : "rgba(255,255,255,0.12)",
          alignItems: "center",
          justifyContent: "center",
          opacity: pressed || disabled ? 0.6 : 1,
          ...(active && {
            shadowColor: HUD.accent,
            shadowOpacity: 0.5,
            shadowRadius: 12,
            shadowOffset: { width: 0, height: 0 },
            elevation: 6,
          }),
        })}
      >
        {children}
      </Pressable>
      {label && (
        <Stamp size={8} color={active ? HUD.accent : HUD.muted}>
          {label}
        </Stamp>
      )}
    </View>
  );
}
