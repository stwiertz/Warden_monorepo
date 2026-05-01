import React, { useEffect, useRef } from "react";
import { Animated, Platform, TextInput, View, type TextInputProps } from "react-native";
import { HUD, HUD_FONT } from "./tokens";
import { Stamp } from "./Stamp";

interface FieldProps extends Omit<TextInputProps, "style"> {
  label: string;
  focused: boolean;
  trailing?: React.ReactNode;
}

/**
 * Tactical-style text field with mono label, focused-state accent border + glow,
 * and a blinking accent caret to the right of the text when focused.
 *
 * Caller manages `focused` (typically with `onFocus` / `onBlur` props passed
 * through). Mirrors the `Field` component in
 * docs/design/warden-mocks/screens/login.jsx.
 */
export function Field({ label, focused, trailing, ...inputProps }: FieldProps) {
  return (
    <View style={{ marginBottom: 12 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 5 }}>
        <Stamp size={9} color={focused ? HUD.accent : HUD.muted}>
          {label}
        </Stamp>
        {focused && (
          <Stamp size={9} color={HUD.accent}>
            ● ACTIVE
          </Stamp>
        )}
      </View>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          paddingHorizontal: 12,
          paddingVertical: Platform.OS === "ios" ? 10 : 6,
          backgroundColor: HUD.surface,
          borderWidth: 1,
          borderColor: focused ? HUD.accent : HUD.line,
          minHeight: 44,
          ...(focused && {
            shadowColor: HUD.accent,
            shadowOpacity: 0.25,
            shadowRadius: 12,
            shadowOffset: { width: 0, height: 0 },
            elevation: 4,
          }),
        }}
      >
        <TextInput
          {...inputProps}
          placeholderTextColor={HUD.dim}
          selectionColor={HUD.accent}
          style={{
            flex: 1,
            fontFamily: HUD_FONT.monoRegular,
            fontSize: 13,
            letterSpacing: 0.5,
            color: HUD.text,
            paddingVertical: 0,
          }}
        />
        {focused && <BlinkingCaret />}
        {trailing && <View style={{ marginLeft: 10 }}>{trailing}</View>}
      </View>
    </View>
  );
}

function BlinkingCaret() {
  const opacity = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.25, duration: 500, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: 500, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);
  return (
    <Animated.View
      style={{
        width: 8,
        height: 14,
        backgroundColor: HUD.accent,
        marginLeft: 4,
        opacity,
      }}
    />
  );
}
