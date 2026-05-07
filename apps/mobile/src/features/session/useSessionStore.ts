import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { zustandMMKVStorage } from "../../shared/services/storage";

interface SessionState {
  currentSessionId: string | null;
  currentEpisodeIndex: number;
  playbackPositionMs: number;
  viewMode: "pov" | "minimap";
  sortOrder: "temporal" | "orange_biggest" | "blue_biggest" | "closest";
  setCurrentSession: (sessionId: string | null) => void;
  setEpisodeIndex: (index: number) => void;
  setPlaybackPosition: (positionMs: number) => void;
  setViewMode: (mode: "pov" | "minimap") => void;
  setSortOrder: (
    order: "temporal" | "orange_biggest" | "blue_biggest" | "closest"
  ) => void;
  resetSession: () => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      currentSessionId: null,
      currentEpisodeIndex: 0,
      playbackPositionMs: 0,
      viewMode: "pov",
      sortOrder: "temporal",
      setCurrentSession: (sessionId) =>
        set({ currentSessionId: sessionId, currentEpisodeIndex: 0, playbackPositionMs: 0 }),
      setEpisodeIndex: (index) => set({ currentEpisodeIndex: index }),
      setPlaybackPosition: (positionMs) =>
        set({ playbackPositionMs: positionMs }),
      setViewMode: (mode) => set({ viewMode: mode }),
      setSortOrder: (order) => set({ sortOrder: order }),
      resetSession: () =>
        set({
          currentSessionId: null,
          currentEpisodeIndex: 0,
          playbackPositionMs: 0,
          viewMode: "pov",
          sortOrder: "temporal",
        }),
    }),
    {
      name: "session-store",
      storage: createJSONStorage(() => zustandMMKVStorage),
    }
  )
);
