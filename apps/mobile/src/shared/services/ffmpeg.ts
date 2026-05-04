import { Paths, Directory } from "expo-file-system";
import type { KeyframeInfo } from "../../features/video-processing/types";

// FFmpeg service — sole entry point for all FFmpeg operations.
// Uses @wokcito/ffmpeg-kit-react-native (FFmpeg 6.0, native AAR from Maven Central,
// 16-kb page-aligned for Android 15+). Auto-links via React Native autolinking — no
// Expo config plugin required.

let FFmpegKit: any;
let FFprobeKit: any;

async function getFFmpeg() {
  if (!FFmpegKit) {
    try {
      const mod = require("@wokcito/ffmpeg-kit-react-native");
      FFmpegKit = mod.FFmpegKit;
      FFprobeKit = mod.FFprobeKit;
    } catch {
      throw new Error(
        "FFmpeg native module not available. Run expo prebuild and build the dev client."
      );
    }
  }
  return { FFmpegKit, FFprobeKit };
}

export interface ExtractKeyframesOptions {
  width?: number; // default 320
  quality?: number; // JPEG quality 1-31, lower=better, default 5
}

/**
 * Get the session-scoped processing directory path string.
 */
export function getProcessingDir(sessionId: string): string {
  const cacheUri = Paths.cache.uri;
  // Ensure no double slashes and strip trailing slash
  const base = cacheUri.endsWith("/") ? cacheUri.slice(0, -1) : cacheUri;
  return `${base}/processing/${sessionId}`;
}

/**
 * Ensure a directory exists, creating it if needed.
 */
function ensureDir(path: string): void {
  const dir = new Directory(path);
  if (!dir.exists) {
    dir.create();
  }
}

/**
 * Extract keyframes (I-frames only) from a video at low resolution.
 * Returns an array of KeyframeInfo with file path and timestamp.
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
  ensureDir(outputDir);

  // Extract keyframes with timestamps in filename using showinfo filter
  const command = [
    `-i "${videoPath}"`,
    `-skip_frame nokey`,
    `-vsync vfr`,
    `-vf "scale=${width}:-1,showinfo"`,
    `-qscale:v ${quality}`,
    `"${outputDir}/frame_%04d.jpg"`,
  ].join(" ");

  const session = await ffmpeg.execute(command);
  const returnCode = await session.getReturnCode();

  if (!returnCode.isValueSuccess()) {
    const output = await session.getOutput();
    throw new Error(`FFmpeg keyframe extraction failed: ${output}`);
  }

  // Parse output to get timestamps
  const logs = await session.getAllLogs();
  const keyframes: KeyframeInfo[] = [];
  let frameIndex = 1;

  for (const log of logs) {
    const message = log.getMessage();
    const ptsMatch = message?.match(/pts_time:(\d+\.?\d*)/);
    if (ptsMatch) {
      const timestampMs = Math.round(parseFloat(ptsMatch[1]) * 1000);
      const paddedIndex = String(frameIndex).padStart(4, "0");
      keyframes.push({
        path: `${outputDir}/frame_${paddedIndex}.jpg`,
        timestampMs,
      });
      frameIndex++;
    }
  }

  // Fallback: if log parsing failed, list directory files
  if (keyframes.length === 0) {
    const dir = new Directory(outputDir);
    if (dir.exists) {
      const entries = dir.list();
      const jpgFiles = entries
        .filter((e) => e.name?.endsWith(".jpg"))
        .map((e) => e.name)
        .sort();

      for (let i = 0; i < jpgFiles.length; i++) {
        keyframes.push({
          path: `${outputDir}/${jpgFiles[i]}`,
          timestampMs: 0,
        });
      }
    }
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

  const command = `-ss ${timestampSec} -i "${videoPath}" -frames:v 1 -q:v 2 "${outputPath}"`;
  const session = await ffmpeg.execute(command);
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

  const session = await probe.execute(
    `-v quiet -show_entries format=duration -of csv=p=0 "${videoPath}"`
  );
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
  const dir = new Directory(getProcessingDir(sessionId));
  if (dir.exists) {
    dir.delete();
  }
}
