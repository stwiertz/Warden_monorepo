import { MMKV } from "react-native-mmkv";
import { type StateStorage } from "zustand/middleware";

export const mmkv = new MMKV({ id: "warden-storage" });

// MMKV key conventions: dot.notation grouped
// auth.token, auth.user, auth.expiresAt
// session.current.id, session.current.position
// prefs.sortOrder, prefs.exportQuality

export const storage = {
  getString: (key: string): string | undefined => mmkv.getString(key),

  setString: (key: string, value: string): void => {
    mmkv.set(key, value);
  },

  getNumber: (key: string): number | undefined => mmkv.getNumber(key),

  setNumber: (key: string, value: number): void => {
    mmkv.set(key, value);
  },

  getBoolean: (key: string): boolean | undefined => mmkv.getBoolean(key),

  setBoolean: (key: string, value: boolean): void => {
    mmkv.set(key, value);
  },

  getObject: <T>(key: string): T | undefined => {
    const json = mmkv.getString(key);
    if (!json) return undefined;
    try {
      return JSON.parse(json) as T;
    } catch {
      return undefined;
    }
  },

  setObject: <T>(key: string, value: T): void => {
    mmkv.set(key, JSON.stringify(value));
  },

  delete: (key: string): void => {
    mmkv.remove(key);
  },

  clearAll: (): void => {
    mmkv.clearAll();
  },
};

// Zustand persist middleware storage adapter
export const zustandMMKVStorage: StateStorage = {
  getItem: (name: string) => {
    return mmkv.getString(name) ?? null;
  },
  setItem: (name: string, value: string) => {
    mmkv.set(name, value);
  },
  removeItem: (name: string) => {
    mmkv.remove(name);
  },
};
