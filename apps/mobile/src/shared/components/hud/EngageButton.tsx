import React from "react";
import { Pressable, Text, type PressableProps } from "react-native";
import { HUD, HUD_FONT } from "./tokens";
import { ArrowRight } from "./Marks";

interface EngageButtonProps extends Omit<PressableProps, "children"> {
  /** Loading state replaces label with "STANDBY…" and dims */
  loading?: boolean;
  /** Override label (default "ENGAGE") */
  label?: string;
}

/**
 * Primary CTA — accent fill, dark mono ALL-CAPS label, right arrow, glow shadow.
 * Used as the screen's "go" action (login, export-now, etc.).
 */
export function EngageButton({ loading = false, label = "ENGAGE", disabled, ...rest }: EngageButtonProps) {
  return (
    <Pressable
      {...rest}
      disabled={loading || disabled}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingVertical: 12,
        paddingHorizontal: 16,
        backgroundColor: HUD.accent,
        opacity: pressed || loading || disabled ? 0.6 : 1,
        shadowColor: HUD.accent,
        shadowOpacity: 0.35,
        shadowRadius: 18,
        shadowOffset: { width: 0, height: 0 },
        elevation: 6,
      })}
    >
      <Text
        style={{
          fontFamily: HUD_FONT.monoBold,
          fontSize: 12,
          letterSpacing: 2.5,
          color: HUD.bg,
        }}
      >
        {loading ? "STANDBY…" : label}
      </Text>
      <ArrowRight size={16} color={HUD.bg} />
    </Pressable>
  );
}
