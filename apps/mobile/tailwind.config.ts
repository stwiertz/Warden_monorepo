import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "./App.tsx"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        background: "#101014",
        surface: "#1A1A1E",
        accent: "#FF6B00",
        "accent-muted": "#CC5500",
        "text-primary": "#F0F0F0",
        "text-secondary": "#8B8F96",
        error: "#EF4444",
        success: "#22C55E",
      },
      fontSize: {
        heading: ["20px", { lineHeight: "28px" }],
        subheading: ["16px", { lineHeight: "24px" }],
        body: ["14px", { lineHeight: "20px" }],
        caption: ["12px", { lineHeight: "16px" }],
      },
      spacing: {
        "touch-min": "44px",
      },
    },
  },
  plugins: [],
};

export default config;
