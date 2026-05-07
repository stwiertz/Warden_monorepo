import React from "react";
import Svg, { Circle, Line, Path, Rect } from "react-native-svg";

// Tactical HUD icon set — mirror of Icon object in
// docs/design/warden-mocks/screens/shared.jsx. All icons share the
// `{ size, color }` signature; default size is 18, color is currentColor-equivalent
// (i.e. caller provides via parent Text or fill prop).

interface IconProps {
  size?: number;
  color?: string;
}

export const Icon = {
  Play: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Path d="M7 5v14l12-7z" />
    </Svg>
  ),
  Pause: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Rect x={6} y={5} width={4} height={14} />
      <Rect x={14} y={5} width={4} height={14} />
    </Svg>
  ),
  Prev: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Path d="M6 5h2v14H6zM20 5L9 12l11 7z" />
    </Svg>
  ),
  Next: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Path d="M16 5h2v14h-2zM4 5l11 7L4 19z" />
    </Svg>
  ),
  Mic: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <Rect x={9} y={3} width={6} height={11} rx={3} />
      <Path d="M5 11a7 7 0 0014 0M12 18v3" />
    </Svg>
  ),
  Scissors: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <Circle cx={6} cy={6} r={3} />
      <Circle cx={6} cy={18} r={3} />
      <Line x1={20} y1={4} x2={8.12} y2={15.88} />
      <Line x1={14.47} y1={14.48} x2={20} y2={20} />
      <Line x1={8.12} y1={8.12} x2={12} y2={12} />
    </Svg>
  ),
  Share: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13" />
    </Svg>
  ),
  Map: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round">
      <Circle cx={12} cy={12} r={9} strokeDasharray="2 2" />
      <Circle cx={12} cy={12} r={4} />
      <Line x1={12} y1={1} x2={12} y2={5} />
      <Line x1={12} y1={19} x2={12} y2={23} />
      <Line x1={1} y1={12} x2={5} y2={12} />
      <Line x1={19} y1={12} x2={23} y2={12} />
      <Circle cx={12} cy={12} r={1.2} fill={color} />
    </Svg>
  ),
  Grid: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.6}>
      <Rect x={3} y={3} width={7} height={7} />
      <Rect x={14} y={3} width={7} height={7} />
      <Rect x={3} y={14} width={7} height={7} />
      <Rect x={14} y={14} width={7} height={7} />
    </Svg>
  ),
  Plus: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round">
      <Path d="M12 5v14M5 12h14" />
    </Svg>
  ),
  Sort: ({ size = 14, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round">
      <Path d="M4 6h16M7 12h10M10 18h4" />
    </Svg>
  ),
  ChevDown: ({ size = 12, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round">
      <Path d="M5 9l7 7 7-7" />
    </Svg>
  ),
  ChevRight: ({ size = 14, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round">
      <Path d="M9 6l6 6-6 6" />
    </Svg>
  ),
  ChevLeft: ({ size = 14, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round">
      <Path d="M15 6l-6 6 6 6" />
    </Svg>
  ),
  Folder: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.5}>
      <Path d="M3 6a1 1 0 011-1h5l2 2h9a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V6z" />
    </Svg>
  ),
  Stop: ({ size = 18, color = "#fff" }: IconProps) => (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Rect x={6} y={6} width={12} height={12} rx={1} />
    </Svg>
  ),
};

export type IconName = keyof typeof Icon;
