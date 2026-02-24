"""FFmpeg-based video utilities for I-frame extraction.

This module handles video decoding via FFmpeg subprocess calls.
It does NOT import OpenCV — only FFmpeg, subprocess, and numpy.
"""

import json
import shutil
import subprocess
import sys
import tempfile

import numpy as np

# Cache for ffmpeg availability check (F15)
_ffmpeg_checked = False


def check_ffmpeg():
    """Validate that ffmpeg and ffprobe are available on PATH.

    Results are cached after the first successful check.

    Raises:
        RuntimeError: If ffmpeg or ffprobe is not found.
    """
    global _ffmpeg_checked
    if _ffmpeg_checked:
        return
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"'{tool}' not found on PATH. Install FFmpeg and ensure it is accessible."
            )
    _ffmpeg_checked = True


def _get_video_info(video_path):
    """Get video dimensions using ffprobe.

    Returns:
        tuple: (width, height) of the video stream.

    Raises:
        RuntimeError: If no video stream is found in the file.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    # F4: validate that a video stream exists
    if not info.get("streams"):
        raise RuntimeError(
            f"No video stream found in '{video_path}'. "
            "Ensure the file is a valid video with at least one video track."
        )
    stream = info["streams"][0]
    return int(stream["width"]), int(stream["height"])


def _get_keyframe_timestamps(video_path):
    """Get PTS timestamps (in seconds) of all keyframes using ffprobe.

    Returns:
        list[float]: Sorted list of keyframe timestamps in seconds.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-skip_frame", "nokey",
        "-show_entries", "frame=pts_time",
        "-of", "csv=p=0",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    timestamps = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip().rstrip(",")
        if line:
            timestamps.append(float(line))
    return timestamps


def extract_iframes(video_path):
    """Yield (numpy_array, timestamp_seconds) for each I-frame in a video.

    Uses ffprobe to get keyframe timestamps and video dimensions, then
    pipes raw BGR24 frames from ffmpeg (keyframes only) via stdout.

    Args:
        video_path: Path to the input video file.

    Yields:
        tuple: (frame, timestamp) where frame is a numpy array of shape
               (height, width, 3) in BGR color order, and timestamp is
               the frame's position in seconds.
    """
    check_ffmpeg()

    width, height = _get_video_info(video_path)
    timestamps = _get_keyframe_timestamps(video_path)

    if not timestamps:
        print("Warning: No keyframes found in video.", file=sys.stderr)
        return

    frame_size = width * height * 3  # BGR24

    cmd = [
        "ffmpeg",
        "-skip_frame", "nokey",
        "-i", str(video_path),
        "-vsync", "0",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "pipe:1",
    ]

    # F9: redirect stderr to a temp file to avoid pipe buffer deadlock
    # while still capturing diagnostics for error reporting
    stderr_file = tempfile.TemporaryFile(mode="w+b")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=stderr_file,
    )

    frames_read = 0
    try:
        for i, ts in enumerate(timestamps):
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                # Fewer frames than expected from ffprobe — end of stream
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
            frames_read += 1
            yield frame, ts
    finally:
        # Check for extra data in pipe (ffmpeg produced more frames than ffprobe)
        leftover = proc.stdout.read(frame_size)
        has_extra = len(leftover) >= frame_size

        proc.stdout.close()
        proc.terminate()
        proc.wait()

        # F1: warn on frame count mismatch between ffprobe and ffmpeg
        if frames_read != len(timestamps) or has_extra:
            print(
                f"Warning: Frame count mismatch — ffprobe reported {len(timestamps)} keyframes, "
                f"ffmpeg produced {'more' if has_extra else frames_read}. "
                "Timestamps may be inaccurate for some frames.",
                file=sys.stderr,
            )

        # F9: log ffmpeg errors if process failed
        if proc.returncode and proc.returncode not in (0, -15, 255):
            # -15 = SIGTERM (expected from our terminate()), 255 = pipe closed
            print(f"Warning: ffmpeg exited with code {proc.returncode}", file=sys.stderr)
            # Read last portion of stderr for diagnostics
            try:
                stderr_file.seek(0, 2)  # seek to end
                size = stderr_file.tell()
                # Read last 2KB of stderr
                stderr_file.seek(max(0, size - 2048))
                stderr_tail = stderr_file.read().decode("utf-8", errors="replace").strip()
                if stderr_tail:
                    for line in stderr_tail.split("\n")[-5:]:
                        print(f"  ffmpeg: {line}", file=sys.stderr)
            except Exception:
                pass

        stderr_file.close()
