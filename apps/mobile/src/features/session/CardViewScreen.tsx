import React, { useState } from "react";
import { Pressable, ScrollView, Text, View, useWindowDimensions } from "react-native";
import {
  HUD,
  HUD_FONT,
  HudBracket,
  Stamp,
  WardenMark,
  Icon,
  MapArt,
} from "../../shared/components";

// Tactical HUD CardView — see docs/design/warden-mocks/screens/screens.jsx :: CardView.
//
// VISUAL STUB — Sprint 3 work. Wire to real session/segment data when
// `getSegmentsForSession` lands. The episode list below is mock data that
// matches the prototype. To use this screen, add it to RootNavigator with a
// `sessionId` route param and replace MOCK_EPISODES with real data fetched
// from sessionRepository / segmentRepository.

interface MockEpisode {
  map: string;
  score: string;
  duration: string;
  win: boolean;
  result: "W" | "L";
  seed: number;
}

const MOCK_EPISODES: MockEpisode[] = [
  { map: "Skyline", score: "13–9", duration: "22:14", win: true, result: "W", seed: 3 },
  { map: "Tank Factory", score: "13–11", duration: "28:42", win: true, result: "W", seed: 7 },
  { map: "Siberia", score: "11–13", duration: "26:08", win: false, result: "L", seed: 12 },
  { map: "Skyline", score: "13–6", duration: "18:51", win: true, result: "W", seed: 18 },
  { map: "Refinery", score: "9–13", duration: "24:33", win: false, result: "L", seed: 22 },
  { map: "Tank Factory", score: "13–10", duration: "23:17", win: true, result: "W", seed: 27 },
  { map: "Siberia", score: "13–12", duration: "31:04", win: true, result: "W", seed: 33 },
  { map: "Refinery", score: "8–13", duration: "21:49", win: false, result: "L", seed: 41 },
];

type Filter = "ALL" | "WINS" | "LOSSES" | "CLOSE";

export function CardViewScreen({ episodes = MOCK_EPISODES }: { episodes?: MockEpisode[] }) {
  const { width, height } = useWindowDimensions();
  const isLandscape = width > height;
  const cols = isLandscape ? 3 : 2;

  const [activeFilter, setActiveFilter] = useState<Filter>("ALL");
  const [activeIdx, setActiveIdx] = useState(0);

  const filtered = episodes.filter((ep) => {
    if (activeFilter === "WINS") return ep.win;
    if (activeFilter === "LOSSES") return !ep.win;
    if (activeFilter === "CLOSE") {
      const [a, b] = ep.score.split("–").map(Number);
      return Math.abs(a - b) <= 2;
    }
    return true;
  });

  return (
    <View style={{ flex: 1, backgroundColor: HUD.bg }}>
      {/* Top brand strip */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          paddingHorizontal: 16,
          paddingTop: 14,
          paddingBottom: 12,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          <WardenMark size={18} />
          <View>
            <Text
              style={{
                fontFamily: HUD_FONT.monoBold,
                fontSize: 12,
                letterSpacing: 2,
                color: HUD.text,
              }}
            >
              WARDEN
            </Text>
            <Stamp size={9}>SCRIM · 24·04·26 · {episodes.length} EPISODES</Stamp>
          </View>
        </View>
        <HudBracket
          dim
          style={{
            paddingHorizontal: 12,
            paddingVertical: 8,
            flexDirection: "row",
            alignItems: "center",
            gap: 8,
            backgroundColor: HUD.surface,
          }}
        >
          <Icon.Sort size={12} color={HUD.muted} />
          <Stamp color={HUD.text}>ORANGE BIGGEST WIN</Stamp>
          <Icon.ChevDown size={10} color={HUD.muted} />
        </HudBracket>
      </View>

      {/* Filter chips */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 6,
          paddingHorizontal: 16,
          paddingBottom: 12,
        }}
      >
        {(["ALL", "WINS", "LOSSES", "CLOSE"] as Filter[]).map((t) => {
          const active = t === activeFilter;
          return (
            <Pressable
              key={t}
              onPress={() => setActiveFilter(t)}
              style={{
                paddingHorizontal: 10,
                paddingVertical: 4,
                borderWidth: 1,
                borderColor: active ? HUD.accent : HUD.line,
                backgroundColor: active ? "rgba(255,107,0,0.08)" : "transparent",
              }}
            >
              <Stamp color={active ? HUD.accent : HUD.muted}>{t}</Stamp>
            </Pressable>
          );
        })}
        <View style={{ flex: 1 }} />
        <Stamp>SES TOTAL · 1:48:32</Stamp>
      </View>

      {/* Grid */}
      <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 16 }}>
        <View
          style={{
            flexDirection: "row",
            flexWrap: "wrap",
            gap: isLandscape ? 14 : 12,
          }}
        >
          {filtered.map((ep, i) => (
            <View
              key={i}
              style={{
                width: `${100 / cols - 2}%`,
              }}
            >
              <EpisodeCard
                ep={ep}
                idx={i}
                active={i === activeIdx}
                onPress={() => setActiveIdx(i)}
              />
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

function EpisodeCard({
  ep,
  idx,
  active,
  onPress,
}: {
  ep: MockEpisode;
  idx: number;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}>
      <HudBracket
        dim={!active}
        style={{
          aspectRatio: 16 / 9,
          backgroundColor: HUD.surface,
          marginBottom: 8,
          overflow: "hidden",
        }}
      >
        <MapArt seed={ep.seed} variant="pov" />

        {/* Score */}
        <Text
          style={{
            position: "absolute",
            top: 8,
            left: 10,
            fontFamily: HUD_FONT.monoBold,
            fontSize: 16,
            letterSpacing: 1,
            color: ep.win ? HUD.accent : HUD.teamBlueSoft,
            textShadowColor: "rgba(0,0,0,0.8)",
            textShadowOffset: { width: 0, height: 1 },
            textShadowRadius: 4,
          }}
        >
          {ep.score}
        </Text>

        {/* W/L tag */}
        <View
          style={{
            position: "absolute",
            top: 8,
            right: 10,
            paddingHorizontal: 6,
            paddingVertical: 2,
            borderWidth: 1,
            borderColor: ep.win ? "rgba(255,107,0,0.4)" : "rgba(123,149,196,0.4)",
          }}
        >
          <Stamp size={10} spacing={1.5} color={ep.win ? HUD.accent : "#7e95c4"}>
            {ep.result}
          </Stamp>
        </View>

        {/* Duration */}
        <Text
          style={{
            position: "absolute",
            bottom: 8,
            left: 10,
            fontFamily: HUD_FONT.monoRegular,
            fontSize: 10,
            color: HUD.text,
            textShadowColor: "rgba(0,0,0,0.8)",
            textShadowOffset: { width: 0, height: 1 },
            textShadowRadius: 4,
          }}
        >
          {ep.duration}
        </Text>

        {/* Episode index */}
        <Text
          style={{
            position: "absolute",
            bottom: 8,
            right: 10,
            fontFamily: HUD_FONT.monoRegular,
            fontSize: 10,
            color: HUD.muted,
          }}
        >
          EP{String(idx + 1).padStart(2, "0")}
        </Text>
      </HudBracket>

      <View
        style={{
          paddingBottom: 6,
          borderBottomWidth: 1,
          borderBottomColor: active ? HUD.accent : HUD.line,
          ...(active && {
            shadowColor: HUD.accent,
            shadowOpacity: 0.4,
            shadowRadius: 6,
            shadowOffset: { width: 0, height: 1 },
            elevation: 2,
          }),
        }}
      >
        <Text
          style={{
            fontFamily: HUD_FONT.monoBold,
            fontSize: 12,
            letterSpacing: 1.5,
            color: HUD.text,
          }}
        >
          {ep.map.toUpperCase()}
        </Text>
      </View>
    </Pressable>
  );
}
