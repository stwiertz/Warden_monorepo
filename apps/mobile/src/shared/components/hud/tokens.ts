// Tactical HUD design tokens — mirror of docs/design/warden-mocks/screens/shared.jsx HUD object.
// Used directly when NativeWind utility classes can't express the value (1px borders,
// rgba blends, glow shadows). Keep in sync with tailwind.config.ts.

export const HUD = {
  bg: "#0a0a0d",
  surface: "#101014",
  elev: "#15151a",
  elev2: "#1c1c22",
  line: "#26262e",
  text: "#F0F0F0",
  muted: "#8a8a92",
  dim: "#52525a",
  accent: "#FF6B00",
  accentSoft: "rgba(255,107,0,0.18)",
  accentDim: "rgba(255,107,0,0.5)",
  teamBlue: "#3a8eff",
  teamBlueSoft: "#5b8aff",

  // White overlays used on dim brackets / corner ticks
  whiteDim: "rgba(255,255,255,0.18)",
} as const;

// Font keys mirror the @expo-google-fonts/* exports loaded in App.tsx.
// Use weighted variants directly via fontFamily — RN doesn't honor fontWeight
// when a custom fontFamily is set on Android, so each weight needs its own key.
export const HUD_FONT = {
  sansRegular: "Roboto_400Regular",
  sansMedium: "Roboto_500Medium",
  sansBold: "Roboto_700Bold",
  monoRegular: "JetBrainsMono_400Regular",
  monoMedium: "JetBrainsMono_500Medium",
  monoBold: "JetBrainsMono_700Bold",
} as const;
