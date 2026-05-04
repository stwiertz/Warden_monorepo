import React, { useCallback, useEffect, useState } from "react";
import {
  Dimensions,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import {
  HUD,
  HUD_FONT,
  HudBracket,
  Stamp,
  CornerTick,
  Field,
  EngageButton,
  BigMark,
  GoogleGlyph,
  Toast,
} from "../../shared/components";
import { useAuthStore } from "./useAuthStore";
import { authService } from "./authService";
import { googleSignInService } from "./googleSignInService";

// Tactical HUD login screen — see docs/design/warden-mocks/screens/login.jsx
// for the canonical visual reference. Layout adapts to landscape (brand left,
// panel right) or portrait (brand top, panel bottom).

export function LoginScreen() {
  // Use screen (not window) dimensions so the keyboard opening doesn't flip
  // the orientation flag and remount the inputs while the user is typing.
  const [screen, setScreen] = useState(() => Dimensions.get("screen"));
  useEffect(() => {
    const sub = Dimensions.addEventListener("change", ({ screen: next }) =>
      setScreen(next)
    );
    return () => sub.remove();
  }, []);
  const isLandscape = screen.width > screen.height;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const { isLoading, error, setError } = useAuthStore();

  const handleLogin = useCallback(() => {
    if (!email.trim() || !password.trim()) {
      setError("Please enter email and password");
      return;
    }
    authService.login(email.trim(), password);
  }, [email, password, setError]);

  const handleGoogleLogin = useCallback(() => {
    googleSignInService.loginWithGoogle();
  }, []);

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={{ flex: 1, backgroundColor: HUD.bg }}
    >
      <View style={{ flex: 1, backgroundColor: HUD.bg }}>
        <CornerTick pos="tl" />
        <CornerTick pos="tr" />
        <CornerTick pos="bl" bottomOffset={24} />
        <CornerTick pos="br" bottomOffset={24} />

        <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
          <View
            style={{
              flex: 1,
              flexDirection: isLandscape ? "row" : "column",
              paddingHorizontal: isLandscape ? 28 : 20,
              paddingTop: isLandscape ? 20 : 24,
              paddingBottom: isLandscape ? 20 : 16,
              gap: isLandscape ? 32 : 0,
            }}
          >
            <BrandBlock landscape={isLandscape} />

            <View
              style={{
                flex: isLandscape ? 0 : 1,
                width: isLandscape ? 340 : "100%",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <HudBracket
                style={{
                  width: "100%",
                  paddingTop: 20,
                  paddingHorizontal: 22,
                  paddingBottom: 22,
                  backgroundColor: "rgba(255,107,0,0.04)",
                }}
              >
                <View
                  style={{
                    flexDirection: "row",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 18,
                  }}
                >
                  <Stamp color={HUD.accent}>▸ ACCESS</Stamp>
                  <Stamp>OP-24-04-26</Stamp>
                </View>

                <Text
                  style={{
                    fontFamily: HUD_FONT.monoBold,
                    fontSize: 16,
                    letterSpacing: 1.5,
                    color: HUD.text,
                    marginBottom: 16,
                  }}
                >
                  LOGIN
                </Text>

                <Field
                  label="EMAIL"
                  value={email}
                  onChangeText={setEmail}
                  focused={emailFocused}
                  onFocus={() => setEmailFocused(true)}
                  onBlur={() => setEmailFocused(false)}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  placeholder="callsign@warden.gg"
                />

                <Field
                  label="PASSWORD"
                  value={password}
                  onChangeText={setPassword}
                  focused={passwordFocused}
                  onFocus={() => setPasswordFocused(true)}
                  onBlur={() => setPasswordFocused(false)}
                  secureTextEntry={!showPassword}
                  placeholder="••••••••••••"
                  trailing={
                    <Pressable onPress={() => setShowPassword((v) => !v)} hitSlop={8}>
                      <Stamp>{showPassword ? "HIDE" : "SHOW"}</Stamp>
                    </Pressable>
                  }
                />

                <View
                  style={{
                    flexDirection: "row",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginTop: 14,
                    marginBottom: 16,
                  }}
                >
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                    <View
                      style={{
                        width: 14,
                        height: 14,
                        borderWidth: 1,
                        borderColor: HUD.accent,
                        backgroundColor: "rgba(255,107,0,0.12)",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Text style={{ color: HUD.accent, fontSize: 9, lineHeight: 12 }}>✓</Text>
                    </View>
                    <Stamp color={HUD.text}>REMEMBER ME</Stamp>
                  </View>
                  <Pressable hitSlop={8}>
                    <Stamp style={{ textDecorationLine: "underline" }}>FORGOT KEY?</Stamp>
                  </Pressable>
                </View>

                <EngageButton onPress={handleLogin} loading={isLoading} />

                <View
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: 10,
                    marginTop: 16,
                    marginBottom: 12,
                  }}
                >
                  <View style={{ flex: 1, height: 1, backgroundColor: HUD.line }} />
                  <Stamp size={9}>OR</Stamp>
                  <View style={{ flex: 1, height: 1, backgroundColor: HUD.line }} />
                </View>

                <Pressable
                  onPress={handleGoogleLogin}
                  disabled={isLoading}
                  style={({ pressed }) => ({
                    paddingVertical: 10,
                    borderWidth: 1,
                    borderColor: HUD.line,
                    backgroundColor: HUD.surface,
                    flexDirection: "row",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    opacity: pressed || isLoading ? 0.6 : 1,
                  })}
                >
                  <GoogleGlyph size={14} />
                  <Stamp
                    spacing={1.5}
                    style={{ lineHeight: 14, includeFontPadding: false }}
                  >
                    CONTINUE WITH GOOGLE
                  </Stamp>
                </Pressable>

                <View style={{ marginTop: 18, flexDirection: "row", justifyContent: "center" }}>
                  <Stamp>NEW HERE? </Stamp>
                  <Pressable hitSlop={8}>
                    <Stamp color={HUD.accent} spacing={1.5}>
                      CREATE ACCOUNT ›
                    </Stamp>
                  </Pressable>
                </View>
              </HudBracket>
            </View>
          </View>
        </ScrollView>

        <Toast
          message={error ?? ""}
          type="error"
          visible={!!error}
          onDismiss={() => setError(null)}
        />
      </View>
    </KeyboardAvoidingView>
  );
}

function BrandBlock({ landscape }: { landscape: boolean }) {
  return (
    <View
      style={{
        flex: landscape ? 1 : 0,
        flexShrink: 0,
        justifyContent: landscape ? "center" : "flex-start",
        paddingTop: landscape ? 0 : 16,
        paddingBottom: landscape ? 0 : 24,
      }}
    >
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 12,
          marginBottom: landscape ? 18 : 14,
        }}
      >
        <BigMark size={landscape ? 36 : 28} />
        <View>
          <Text
            style={{
              fontFamily: HUD_FONT.monoBold,
              fontSize: landscape ? 22 : 18,
              letterSpacing: 4,
              color: HUD.text,
            }}
          >
            WARDEN
          </Text>
          <Stamp size={9} style={{ marginTop: 2 }}>
            MATCH ANALYSIS · v0.4.1
          </Stamp>
        </View>
      </View>
      <Text
        style={{
          fontFamily: HUD_FONT.sansRegular,
          fontSize: landscape ? 14 : 13,
          color: HUD.muted,
          lineHeight: landscape ? 21 : 19,
          maxWidth: 320,
        }}
      >
        Sign in to sync sessions, voice notes, and clips across headset, phone, and coach review.
      </Text>
    </View>
  );
}
