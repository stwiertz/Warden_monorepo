import React from "react";
import Svg, { Circle, G, Line, Path, Rect } from "react-native-svg";
import { HUD } from "./tokens";

// Brand mark — small (in toolbars / status strips). Hex outline + chevron + center pip.
export function WardenMark({ size = 18 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 2L21 7v10l-9 5-9-5V7l9-5z" stroke={HUD.accent} strokeWidth={1.4} />
      <Path
        d="M8 9l4 6 4-6"
        stroke={HUD.text}
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// Brand mark — big (login hero). Adds inner hex + center pip for depth.
export function BigMark({ size = 36 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 36 36" fill="none">
      <Path d="M18 2L32 10v16l-14 8-14-8V10L18 2z" stroke={HUD.accent} strokeWidth={1.4} />
      <Path d="M18 6L28 12v12l-10 6-10-6V12L18 6z" stroke="rgba(255,107,0,0.4)" strokeWidth={0.8} />
      <Path
        d="M11 14l7 10 7-10"
        stroke={HUD.text}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Circle cx={18} cy={18} r={1.5} fill={HUD.accent} />
    </Svg>
  );
}

// Center reticle — used at POV center and as the active-state minimap mark.
export function Reticle({ size = 64, color = HUD.accent }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <Circle cx={32} cy={32} r={24} stroke="rgba(255,107,0,0.4)" strokeWidth={0.8} strokeDasharray="2 3" />
      <Line x1={32} y1={4} x2={32} y2={14} stroke={color} strokeWidth={1} />
      <Line x1={32} y1={50} x2={32} y2={60} stroke={color} strokeWidth={1} />
      <Line x1={4} y1={32} x2={14} y2={32} stroke={color} strokeWidth={1} />
      <Line x1={50} y1={32} x2={60} y2={32} stroke={color} strokeWidth={1} />
    </Svg>
  );
}

// Reticle-style L-bracket clip handle — open-corner faces into clip region.
export function ClipHandle({ dir }: { dir: "start" | "end" }) {
  return (
    <Svg width={14} height={26} viewBox="0 0 14 26">
      <G stroke={HUD.accent} strokeWidth={1.4} fill="none">
        <Path d={dir === "start" ? "M9 1 H1 V25 H9" : "M5 1 H13 V25 H5"} />
        <Line x1={7} y1={9} x2={7} y2={17} strokeWidth={1.6} />
      </G>
    </Svg>
  );
}

// Small arrow used on the ENGAGE primary CTA + various right-pointing affordances.
export function ArrowRight({ size = 16, color = "#0a0a0d" }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={(size * 12) / 16} viewBox="0 0 16 12" fill="none">
      <Path
        d="M1 6H14M9 1L14 6L9 11"
        stroke={color}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// Google G glyph — color-true variant. Use for the "Continue with Google" SSO row.
export function GoogleGlyph({ size = 14 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 18 18">
      <Path
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 01-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
        fill="#4285F4"
      />
      <Path
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.83.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 009 18z"
        fill="#34A853"
      />
      <Path
        d="M3.97 10.72A5.4 5.4 0 013.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 000 9c0 1.45.35 2.83.96 4.05l3.01-2.33z"
        fill="#FBBC04"
      />
      <Path
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 009 0 9 9 0 00.96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
        fill="#EA4335"
      />
    </Svg>
  );
}

// Recon-grid backdrop — 32px dotted/lined SVG pattern, low opacity. Use behind
// hero surfaces (login). Implemented as a tiled <Line> grid since react-native-svg
// doesn't support <pattern> reliably across platforms.
export function ReconGrid({ width, height, opacity = 0.5 }: { width: number; height: number; opacity?: number }) {
  const step = 32;
  const cols = Math.ceil(width / step);
  const rows = Math.ceil(height / step);
  const lines: React.ReactElement[] = [];
  for (let i = 0; i <= cols; i++) {
    lines.push(
      <Line
        key={`v${i}`}
        x1={i * step}
        y1={0}
        x2={i * step}
        y2={height}
        stroke={HUD.elev2}
        strokeWidth={0.5}
      />
    );
  }
  for (let j = 0; j <= rows; j++) {
    lines.push(
      <Line
        key={`h${j}`}
        x1={0}
        y1={j * step}
        x2={width}
        y2={j * step}
        stroke={HUD.elev2}
        strokeWidth={0.5}
      />
    );
  }
  return (
    <Svg width={width} height={height} style={{ opacity }} pointerEvents="none">
      {lines}
    </Svg>
  );
}

// Deterministic waveform — used as a placeholder for voice-clip audio
export function Waveform({
  seed = 1,
  bars = 28,
  color = HUD.muted,
  height = 18,
}: {
  seed?: number;
  bars?: number;
  color?: string;
  height?: number;
}) {
  const r = (n: number) => {
    const x = Math.sin(seed * 13 + n * 1.7) * 10000;
    return x - Math.floor(x);
  };
  const barWidth = 2;
  const gap = 2;
  const totalWidth = bars * barWidth + (bars - 1) * gap;
  return (
    <Svg width={totalWidth} height={height}>
      {Array.from({ length: bars }).map((_, i) => {
        const h = 3 + r(i) * (height - 3);
        return (
          <Rect
            key={i}
            x={i * (barWidth + gap)}
            y={(height - h) / 2}
            width={barWidth}
            height={h}
            fill={color}
            rx={1}
            opacity={0.5 + r(i + 100) * 0.5}
          />
        );
      })}
    </Svg>
  );
}

// Radar progress ring — used on the Processing screen.
export function RadarRing({
  size = 140,
  progress = 0,
}: {
  size?: number;
  progress?: number;
}) {
  const cx = size / 2;
  const cy = size / 2;
  const r = (size / 140) * 56;
  const c = 2 * Math.PI * r;
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none">
      <Circle cx={cx} cy={cy} r={(size / 140) * 64} stroke="rgba(255,255,255,0.08)" strokeWidth={1} />
      <Circle cx={cx} cy={cy} r={(size / 140) * 46} stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
      <Circle cx={cx} cy={cy} r={(size / 140) * 28} stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
      <Line x1={cx} y1={6} x2={cx} y2={size - 6} stroke="rgba(255,255,255,0.06)" strokeWidth={0.5} />
      <Line x1={6} y1={cy} x2={size - 6} y2={cy} stroke="rgba(255,255,255,0.06)" strokeWidth={0.5} />
      <Circle
        cx={cx}
        cy={cy}
        r={r}
        stroke={HUD.accent}
        strokeWidth={2}
        strokeDasharray={`${c * progress} ${c}`}
        strokeDashoffset={c * 0.25}
        transform={`rotate(-90 ${cx} ${cy})`}
        strokeLinecap="butt"
        fill="none"
      />
      <Line
        x1={cx}
        y1={cy}
        x2={cx}
        y2={(size / 140) * 14}
        stroke={HUD.accent}
        strokeWidth={1}
        opacity={0.7}
        transform={`rotate(120 ${cx} ${cy})`}
      />
      <Circle cx={cx} cy={cy} r={2.5} fill={HUD.accent} />
    </Svg>
  );
}
