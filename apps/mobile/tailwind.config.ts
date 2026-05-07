import type { Config } from "tailwindcss";

// Tactical HUD palette — see docs/design/warden-mocks/ for canonical reference.
// Accent values are also exported as flat keys so existing screens don't break.
const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "./App.tsx"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // Tactical HUD canonical tokens
        bg: "#0a0a0d",
        surface: "#101014",
        elev: "#15151a",
        elev2: "#1c1c22",
        line: "#26262e",
        text: "#F0F0F0",
        muted: "#8a8a92",
        dim: "#52525a",
        accent: "#FF6B00",
        "accent-soft": "rgba(255,107,0,0.18)",
        "accent-dim": "rgba(255,107,0,0.5)",
        "team-blue": "#3a8eff",
        "team-blue-soft": "#5b8aff",

        // Legacy aliases — still in use by older screens
        background: "#0a0a0d",
        "accent-muted": "#CC5500",
        "text-primary": "#F0F0F0",
        "text-secondary": "#8a8a92",
        error: "#EF4444",
        success: "#22C55E",
      },
      fontFamily: {
        // Loaded via @expo-google-fonts/* — see hudFonts loader
        sans: ["Roboto", "Helvetica Neue", "system-ui", "sans-serif"],
        mono: ["JetBrainsMono", "SF Mono", "Roboto Mono", "monospace"],
      },
      fontSize: {
        heading: ["20px", { lineHeight: "28px" }],
        subheading: ["16px", { lineHeight: "24px" }],
        body: ["14px", { lineHeight: "20px" }],
        caption: ["12px", { lineHeight: "16px" }],
        stamp: ["10px", { lineHeight: "14px", letterSpacing: "1px" }],
      },
      spacing: {
        "touch-min": "44px",
      },
      letterSpacing: {
        stamp: "1px",
        tactical: "1.5px",
        wordmark: "4px",
      },
    },
  },
  plugins: [],
};

export default config;
