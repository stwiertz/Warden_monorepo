import { Paths, Directory } from "expo-file-system";
import type { KeyframeInfo } from "../../features/video-processing/types";

// FFmpeg service — sole entry point for all FFmpeg operations.
// Uses @wokcito/ffmpeg-kit-react-native (FFmpeg-kit 6.1.4 native AAR from
// Maven Central, 16-kb page-aligned for Android 15+). Auto-links via React
// Native autolinking — no Expo config plugin required.

interface FFmpegSession {
  getReturnCode(): Promise<{ isValueSuccess(): boolean }>;
  getOutput(): Promise<string>;
  getAllLogs(): Promise<Array<{ getMessage(): string | undefined }>>;
}

interface FFmpegStatistics {
  getTime?(): number;
}

type CompleteCallback = (session: FFmpegSession) => void;
type StatisticsCallback = (statistics: FFmpegStatistics) => void;

interface FFmpegKitApi {
  executeWithArguments(args: string[]): Promise<FFmpegSession>;
  executeWithArgumentsAsync(
    args: string[],
    completeCallback?: CompleteCallback,
    logCallback?: undefined,
    statisticsCallback?: StatisticsCallback
  ): Promise<FFmpegSession>;
}

interface FFprobeKitApi {
  executeWithArguments(args: string[]): Promise<FFmpegSession>;
}

interface FFmpegKitConfigApi {
  setLogRedirectionStrategy(strategy: number): void;
}

let FFmpegKit: FFmpegKitApi | undefined;
let FFprobeKit: FFprobeKitApi | undefined;

async function getFFmpeg(): Promise<{
  FFmpegKit: FFmpegKitApi;
  FFprobeKit: FFprobeKitApi;
}> {
  if (!FFmpegKit || !FFprobeKit) {
    let mod: {
      FFmpegKit?: FFmpegKitApi;
      FFprobeKit?: FFprobeKitApi;
      FFmpegKitConfig?: FFmpegKitConfigApi;
      LogRedirectionStrategy?: { NEVER_PRINT_LOGS?: number };
    };
    try {
      mod = require("@wokcito/ffmpeg-kit-react-native");
    } catch {
      throw new Error(
        "FFmpeg native module not available. Run expo prebuild and build the dev client."
      );
    }
    if (!mod?.FFmpegKit || !mod?.FFprobeKit) {
      throw new Error(
        "FFmpeg native module loaded but FFmpegKit/FFprobeKit exports missing — check @wokcito/ffmpeg-kit-react-native version."
      );
    }
    // Silence the bridge-to-console log forwarding. Sessions still retain
    // every log line, so getAllLogs() / showinfo pts_time parsing keep
    // working — we just don't spam Metro with FFmpeg's per-frame output.
    const neverPrint = mod.LogRedirectionStrategy?.NEVER_PRINT_LOGS;
    if (mod.FFmpegKitConfig && typeof neverPrint === "number") {
      try {
        mod.FFmpegKitConfig.setLogRedirectionStrategy(neverPrint);
      } catch {
        // Best-effort; if the strategy can't be set we still get correct
        // results, just with verbose console output.
      }
    }
    FFmpegKit = mod.FFmpegKit;
    FFprobeKit = mod.FFprobeKit;
  }
  return { FFmpegKit, FFprobeKit };
}

export interface ExtractKeyframesOptions {
  width?: number; // default 320
  quality?: number; // JPEG quality 1-31, lower=better, default 5
  // Total video duration in ms. Required to drive incremental progress.
  totalDurationMs?: number;
  // Fires roughly every ~500ms with a 0..100 percentage based on the
  // currently-processed timestamp. Only invoked when totalDurationMs is also
  // provided.
  onProgress?: (percent: number) => void;
}

// Reject session ids that could escape the cache root via path traversal or
// resolve to the parent processing directory itself.
const SAFE_SESSION_ID = /^[a-zA-Z0-9_-]+$/;

function assertSafeSessionId(sessionId: string): void {
  if (!sessionId || !SAFE_SESSION_ID.test(sessionId)) {
    throw new Error(`Invalid sessionId: ${JSON.stringify(sessionId)}`);
  }
}

// FFmpeg's image2 muxer (and several other muxers) call fopen() with the
// literal filename and don't strip URI schemes — passing "file:///foo.jpg"
// fails with "Could not open file : file:///foo.jpg". Inputs go through
// avio_open which understands file://, but for consistency and safety we
// strip the scheme on every path handed to FFmpeg.
function toFFmpegPath(uri: string): string {
  return uri.startsWith("file://") ? uri.slice("file://".length) : uri;
}

/**
 * Get the session-scoped processing directory path string.
 */
export function getProcessingDir(sessionId: string): string {
  assertSafeSessionId(sessionId);
  const cacheUri = Paths.cache.uri;
  const base = cacheUri.endsWith("/") ? cacheUri.slice(0, -1) : cacheUri;
  return `${base}/processing/${sessionId}`;
}

function ensureDir(path: string): void {
  const dir = new Directory(path);
  if (dir.exists) return;
  try {
    // intermediates: true is required — the first run for a session creates
    // both processing/<id>/ and processing/<id>/keyframes/ in one shot.
    // Without it, the inner create silently failed and FFmpeg's I/O error
    // surfaced as the only symptom.
    dir.create({ intermediates: true });
  } catch (error) {
    // Race against another concurrent create is benign once the dir exists.
    if (!dir.exists) {
      throw new Error(
        `Failed to create directory ${path}: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }
}

function clearDir(path: string): void {
  const dir = new Directory(path);
  if (dir.exists) {
    dir.delete();
  }
}

// Run an FFmpeg session and resolve when execution completes. If a duration
// and progress callback are supplied, attach a statistics callback that
// translates the kit's per-frame time-in-ms into a 0..100 percentage.
function runFFmpegWithProgress(
  ffmpeg: FFmpegKitApi,
  args: string[],
  totalDurationMs: number | undefined,
  onProgress: ((percent: number) => void) | undefined
): Promise<FFmpegSession> {
  if (!onProgress || !totalDurationMs || totalDurationMs <= 0) {
    return ffmpeg.executeWithArguments(args);
  }
  return new Promise<FFmpegSession>((resolve, reject) => {
    let lastReported = -1;
    ffmpeg
      .executeWithArgumentsAsync(
        args,
        (session) => resolve(session),
        undefined,
        (stats) => {
          const t = stats.getTime?.() ?? 0;
          if (t < 0) return;
          const pct = Math.min(100, Math.max(0, (t / totalDurationMs) * 100));
          // Throttle: only fire on integer percentage changes to keep the
          // React re-render volume bounded for long videos.
          const next = Math.floor(pct);
          if (next !== lastReported) {
            lastReported = next;
            onProgress(next);
          }
        }
      )
      .catch(reject);
  });
}

/**
 * Extract keyframes (I-frames only) from a video at low resolution.
 * Returns an array of KeyframeInfo with file path and timestamp.
 *
 * Re-running with the same sessionId clears the prior keyframes/ output to
 * avoid silent overwrite of `frame_%04d.jpg` from a previous attempt.
 */
export async function extractKeyframes(
  videoPath: string,
  sessionId: string,
  options?: ExtractKeyframesOptions
): Promise<KeyframeInfo[]> {
  const { FFmpegKit: ffmpeg } = await getFFmpeg();
  const width = options?.width ?? 320;
  const quality = options?.quality ?? 5;

  const outputDir = `${getProcessingDir(sessionId)}/keyframes`;
  clearDir(outputDir);
  ensureDir(outputDir);

  // Pre-tokenized arguments — no shell parsing, no quoting hazards.
  // -skip_frame is a decoder option and MUST appear before -i so it binds to
  // the input (otherwise FFmpeg tries to apply it to the JPEG encoder and
  // errors: "Codec AVOption skip_frame ... is not an encoding option").
  // -fps_mode replaces the deprecated -vsync.
  const args = [
    "-y",
    "-skip_frame", "nokey",
    "-i", toFFmpegPath(videoPath),
    "-fps_mode", "vfr",
    "-vf", `scale=${width}:-1,showinfo`,
    "-qscale:v", String(quality),
    `${toFFmpegPath(outputDir)}/frame_%04d.jpg`,
  ];

  const session = await runFFmpegWithProgress(
    ffmpeg,
    args,
    options?.totalDurationMs,
    options?.onProgress
  );
  const returnCode = await session.getReturnCode();

  if (!returnCode.isValueSuccess()) {
    const output = await session.getOutput();
    throw new Error(`FFmpeg keyframe extraction failed: ${output}`);
  }

  // Pair pts_time log entries with the on-disk files written by ffmpeg.
  // showinfo emits one pts_time per decoded keyframe; ffmpeg writes one
  // frame_NNNN.jpg per such frame in the same order.
  const logs = await session.getAllLogs();
  const timestamps: number[] = [];
  for (const log of logs) {
    const ptsMatch = log.getMessage()?.match(/pts_time:(\d+\.?\d*)/);
    if (ptsMatch) {
      timestamps.push(Math.round(parseFloat(ptsMatch[1]) * 1000));
    }
  }

  const dir = new Directory(outputDir);
  const writtenFiles = dir.exists
    ? dir
        .list()
        .map((e) => e.name)
        .filter((n): n is string => !!n && n.endsWith(".jpg"))
        .sort()
    : [];

  // If the file count doesn't match the timestamp count, the showinfo↔file
  // pairing has desynchronized — return the intersection rather than fabricating.
  // Downstream stages need real timestamps; fabricated zeros silently corrupt
  // black-screen detection (Story 2.3) and segmentation (Story 2.5).
  if (writtenFiles.length === 0) {
    throw new Error(
      "FFmpeg keyframe extraction produced no output files; check video path and codec."
    );
  }
  if (timestamps.length === 0) {
    throw new Error(
      "FFmpeg keyframe extraction produced files but no pts_time logs; cannot pair timestamps."
    );
  }

  const pairedCount = Math.min(timestamps.length, writtenFiles.length);
  const keyframes: KeyframeInfo[] = [];
  for (let i = 0; i < pairedCount; i++) {
    keyframes.push({
      path: `${outputDir}/${writtenFiles[i]}`,
      timestampMs: timestamps[i],
    });
  }
  return keyframes;
}

/**
 * Extract a single frame at a specific timestamp.
 */
export async function extractFrameAt(
  videoPath: string,
  timestampMs: number,
  outputPath: string
): Promise<string> {
  const { FFmpegKit: ffmpeg } = await getFFmpeg();
  const timestampSec = (timestampMs / 1000).toFixed(3);

  const parentDir = outputPath.substring(0, outputPath.lastIndexOf("/"));
  ensureDir(parentDir);

  const args = [
    "-y",
    "-ss", timestampSec,
    "-i", toFFmpegPath(videoPath),
    "-frames:v", "1",
    "-q:v", "2",
    toFFmpegPath(outputPath),
  ];
  const session = await ffmpeg.executeWithArguments(args);
  const returnCode = await session.getReturnCode();

  if (!returnCode.isValueSuccess()) {
    throw new Error(`FFmpeg frame extraction failed at ${timestampMs}ms`);
  }

  return outputPath;
}

/**
 * Get video duration in milliseconds.
 */
export async function getVideoDuration(videoPath: string): Promise<number> {
  const { FFprobeKit: probe } = await getFFmpeg();

  const session = await probe.executeWithArguments([
    "-v", "quiet",
    "-show_entries", "format=duration",
    "-of", "csv=p=0",
    toFFmpegPath(videoPath),
  ]);
  const output = await session.getOutput();
  const durationSec = parseFloat(output.trim());

  if (isNaN(durationSec)) {
    throw new Error("Could not determine video duration");
  }

  return Math.round(durationSec * 1000);
}

export interface GopInfo {
  averageGopSeconds: number;
  // True when the keyframe interval is short enough for the KDA gameDetector
  // to track game state reliably (≤ 2 s per Story 7.5 AC 6). When false, the
  // pipeline switches to the long-GOP black-screen fallback.
  hasShortGop: boolean;
}

/**
 * Probe the keyframe interval of `videoPath`. Implementation reads
 * `pts_time` for every I-frame via FFprobe and averages the deltas. A video
 * with fewer than 2 keyframes returns `hasShortGop: false` (we can't probe
 * meaningfully — let the fallback handle it).
 */
export async function getGopInfo(videoPath: string): Promise<GopInfo> {
  const { FFprobeKit: probe } = await getFFmpeg();
  const session = await probe.executeWithArguments([
    "-v", "error",
    "-select_streams", "v:0",
    "-skip_frame", "nokey",
    "-show_entries", "frame=pts_time",
    "-of", "csv=p=0",
    toFFmpegPath(videoPath),
  ]);
  const returnCode = await session.getReturnCode();
  if (!returnCode.isValueSuccess()) {
    throw new Error("FFprobe failed while probing keyframe interval");
  }
  const output = await session.getOutput();
  const timestamps = output
    .trim()
    .split(/\s+/)
    .map((s) => parseFloat(s))
    .filter((n) => Number.isFinite(n));
  if (timestamps.length < 2) {
    return { averageGopSeconds: Infinity, hasShortGop: false };
  }
  let sum = 0;
  for (let i = 1; i < timestamps.length; i++) sum += timestamps[i] - timestamps[i - 1];
  const avg = sum / (timestamps.length - 1);
  return { averageGopSeconds: avg, hasShortGop: avg <= 2.0 };
}

/**
 * Clean up session processing files.
 */
export function cleanupProcessingFiles(sessionId: string): void {
  // assertSafeSessionId is invoked transitively by getProcessingDir; calling
  // it here too keeps the precondition local at the destructive call site.
  assertSafeSessionId(sessionId);
  const dir = new Directory(getProcessingDir(sessionId));
  if (dir.exists) {
    dir.delete();
  }
}

// Internal export for unit tests — not part of the public service contract.
export const __testing = { assertSafeSessionId, SAFE_SESSION_ID };
