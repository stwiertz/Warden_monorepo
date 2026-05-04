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

interface FFmpegKitApi {
  executeWithArguments(args: string[]): Promise<FFmpegSession>;
}

interface FFprobeKitApi {
  executeWithArguments(args: string[]): Promise<FFmpegSession>;
}

let FFmpegKit: FFmpegKitApi | undefined;
let FFprobeKit: FFprobeKitApi | undefined;

async function getFFmpeg(): Promise<{
  FFmpegKit: FFmpegKitApi;
  FFprobeKit: FFprobeKitApi;
}> {
  if (!FFmpegKit || !FFprobeKit) {
    let mod: { FFmpegKit?: FFmpegKitApi; FFprobeKit?: FFprobeKitApi };
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
    FFmpegKit = mod.FFmpegKit;
    FFprobeKit = mod.FFprobeKit;
  }
  return { FFmpegKit, FFprobeKit };
}

export interface ExtractKeyframesOptions {
  width?: number; // default 320
  quality?: number; // JPEG quality 1-31, lower=better, default 5
}

// Reject session ids that could escape the cache root via path traversal or
// resolve to the parent processing directory itself.
const SAFE_SESSION_ID = /^[a-zA-Z0-9_-]+$/;

function assertSafeSessionId(sessionId: string): void {
  if (!sessionId || !SAFE_SESSION_ID.test(sessionId)) {
    throw new Error(`Invalid sessionId: ${JSON.stringify(sessionId)}`);
  }
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
  try {
    if (!dir.exists) {
      dir.create();
    }
  } catch {
    // create() races are benign; a subsequent file write will surface a real failure.
  }
}

function clearDir(path: string): void {
  const dir = new Directory(path);
  if (dir.exists) {
    dir.delete();
  }
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
  const args = [
    "-y",
    "-i", videoPath,
    "-skip_frame", "nokey",
    "-vsync", "vfr",
    "-vf", `scale=${width}:-1,showinfo`,
    "-qscale:v", String(quality),
    `${outputDir}/frame_%04d.jpg`,
  ];

  const session = await ffmpeg.executeWithArguments(args);
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
    "-i", videoPath,
    "-frames:v", "1",
    "-q:v", "2",
    outputPath,
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
    videoPath,
  ]);
  const output = await session.getOutput();
  const durationSec = parseFloat(output.trim());

  if (isNaN(durationSec)) {
    throw new Error("Could not determine video duration");
  }

  return Math.round(durationSec * 1000);
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
