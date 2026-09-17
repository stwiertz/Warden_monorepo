import { Paths, Directory } from "expo-file-system";

// FFmpeg service — sole entry point for all FFmpeg operations.
// Uses @wokcito/ffmpeg-kit-react-native (FFmpeg-kit 6.1.4 native AAR from
// Maven Central, 16-kb page-aligned for Android 15+). Auto-links via React
// Native autolinking — no Expo config plugin required.

interface FFmpegSession {
  getReturnCode(): Promise<{ isValueSuccess(): boolean }>;
  getOutput(): Promise<string>;
}

// Story 12.4c dropped `executeWithArgumentsAsync` and its statistics callback
// with `extractKeyframes`: the progress they carried was the keyframe-extraction
// percentage, and the engine reports its own progress as device events from the
// native side. Every surviving call is a short synchronous one.
interface FFmpegKitApi {
  executeWithArguments(args: string[]): Promise<FFmpegSession>;
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
    // every log line; we just don't spam Metro with FFmpeg's per-frame output.
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

// 🔴 STORY 12.4c REMOVED `extractKeyframes` AND `getGopInfo`, AND THAT IS THE
// POINT OF THE STORY, NOT A TIDY-UP.
//
// `extractKeyframes` decoded every keyframe to `./keyframes/frame_%04d.jpg` on
// disk so a second pass could re-load each JPEG through OpenCV. The bound engine
// decodes keyframes in RAM via MediaCodec and evaluates them in the same pass,
// so the JPEGs, the disk round-trip, the showinfo<->filename timestamp pairing
// and the `keyframes` stage all went with it (12.4c AC7, point 3).
//
// `getGopInfo` existed for ONE branch: `hasShortGop` chose between the KDA
// detector and the two-pass black-screen fallback. The engine decodes keyframes
// ONLY, by construction, and never holds the frame set — so the branch has no
// meaning and `blackScreenDetector.ts` is deleted (AC0e). `mobile-AUTO-SLICE-001`'s
// "with reduced sampling on weak hardware" clause re-attaches to ladder rung 1
// step 1b (keyframe decimation), which is where Story 12.3 put it.
//
// What is KEPT is what the results stage and the session lifecycle still use:
// `extractFrameAt`, `getVideoDuration`, `getProcessingDir`,
// `cleanupProcessingFiles` and the `assertSafeSessionId` gate every path goes
// through.

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
