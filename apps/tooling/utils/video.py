"""FFmpeg-based video utilities for I-frame extraction.

This module handles video decoding via FFmpeg subprocess calls.
It does NOT import OpenCV — only FFmpeg, subprocess, and numpy.
"""

import json
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

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


def get_video_info(video_path):
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


def extract_iframes(video_path, profile_stats=None):
    """Yield (numpy_array, timestamp_seconds) for each I-frame in a video.

    Uses ffprobe to get keyframe timestamps and video dimensions, then
    pipes raw BGR24 frames from ffmpeg (keyframes only) via stdout.

    Args:
        video_path: Path to the input video file.
        profile_stats: Optional dict to accumulate timing data into.
            When None (default), no timing overhead is added.

    Yields:
        tuple: (frame, timestamp) where frame is a numpy array of shape
               (height, width, 3) in BGR color order, and timestamp is
               the frame's position in seconds.
    """
    check_ffmpeg()

    if profile_stats is not None:
        t0 = time.perf_counter()
    width, height = get_video_info(video_path)
    if profile_stats is not None:
        profile_stats["ffprobe_info"] = time.perf_counter() - t0

    if profile_stats is not None:
        t0 = time.perf_counter()
    timestamps = _get_keyframe_timestamps(video_path)
    if profile_stats is not None:
        profile_stats["ffprobe_keyframes"] = time.perf_counter() - t0

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

    if profile_stats is not None:
        profile_stats["ffmpeg_read"] = 0.0

    frames_read = 0
    try:
        for i, ts in enumerate(timestamps):
            if profile_stats is not None:
                t0 = time.perf_counter()
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                # Fewer frames than expected from ffprobe — end of stream
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
            if profile_stats is not None:
                profile_stats["ffmpeg_read"] += time.perf_counter() - t0
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


def _stderr_timestamp_reader(stderr_pipe, ts_queue):
    """Read ffmpeg stderr line-by-line, parse showinfo pts_time values.

    Thread target function. Pushes parsed float timestamps into ts_queue.
    Pushes None sentinel when the stream closes.
    """
    pts_re = re.compile(r"pts_time:(\S+)")
    try:
        for raw_line in stderr_pipe:
            line = raw_line.decode("utf-8", errors="replace")
            m = pts_re.search(line)
            if m:
                ts_queue.put(float(m.group(1)))
    except Exception:
        pass
    finally:
        ts_queue.put(None)


def extract_iframes_scaled(video_path, target_height, profile_stats=None):
    """Yield (numpy_array, timestamp_seconds) for each I-frame, scaled to target_height.

    Single-pass architecture: uses ffmpeg's showinfo filter to extract timestamps
    from stderr while piping scaled frames from stdout. No separate ffprobe
    keyframe scan is needed.

    Args:
        video_path: Path to the input video file.
        target_height: Desired output height in pixels (e.g. 360).
        profile_stats: Optional dict to accumulate timing data into.

    Yields:
        tuple: (frame, timestamp) where frame is a numpy array of shape
               (scaled_h, scaled_w, 3) in BGR color order, and timestamp is
               the frame's PTS position in seconds.
    """
    check_ffmpeg()

    if profile_stats is not None:
        t0 = time.perf_counter()
    src_w, src_h = get_video_info(video_path)
    if profile_stats is not None:
        profile_stats["ffprobe_info"] = time.perf_counter() - t0

    # Compute scaled dimensions matching ffmpeg's even-number rounding
    scaled_w = round(src_w * target_height / src_h / 2) * 2
    scaled_h = target_height
    frame_size = scaled_w * scaled_h * 3  # BGR24

    cmd = [
        "ffmpeg",
        "-skip_frame", "nokey",
        "-v", "info",
        "-nostats",
        "-i", str(video_path),
        "-vf", f"showinfo,scale={scaled_w}:{scaled_h}",
        "-vsync", "0",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "pipe:1",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    ts_queue = queue.Queue()
    reader_thread = threading.Thread(
        target=_stderr_timestamp_reader,
        args=(proc.stderr, ts_queue),
        daemon=True,
    )
    reader_thread.start()

    if profile_stats is not None:
        profile_stats["ffmpeg_read"] = 0.0

    try:
        while True:
            if profile_stats is not None:
                t0 = time.perf_counter()
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break
            try:
                ts = ts_queue.get(timeout=10)
            except queue.Empty:
                print(
                    "Warning: Timed out waiting for timestamp from ffmpeg showinfo. "
                    "Stopping frame extraction.",
                    file=sys.stderr,
                )
                break
            if ts is None:
                # Sentinel — stderr closed before stdout exhausted
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((scaled_h, scaled_w, 3))
            if profile_stats is not None:
                profile_stats["ffmpeg_read"] += time.perf_counter() - t0
            yield frame, ts
    finally:
        proc.stdout.close()
        proc.stderr.close()
        proc.terminate()
        proc.wait()
        reader_thread.join(timeout=5)

        if proc.returncode and proc.returncode not in (0, -15, 255):
            print(f"Warning: ffmpeg exited with code {proc.returncode}", file=sys.stderr)


def extract_frame_at_timestamp(video_path, timestamp, width, height):
    """Extract a single full-resolution frame at an exact keyframe timestamp.

    Uses input seeking (-ss before -i) which fast-seeks to the nearest keyframe.
    Since timestamps are keyframe PTS values, seek lands exactly on the target frame.

    Args:
        video_path: Path to the input video file.
        timestamp: PTS timestamp in seconds (float).
        width: Source video width in pixels.
        height: Source video height in pixels.

    Returns:
        numpy array of shape (height, width, 3) in BGR color order.

    Raises:
        RuntimeError: If the extracted frame size doesn't match expected dimensions.
    """
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-ss", f"{timestamp:.6f}",
        "-i", str(video_path),
        "-frames:v", "1",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "pipe:1",
    ]

    result = subprocess.run(cmd, capture_output=True, check=True)
    expected_size = width * height * 3
    if len(result.stdout) != expected_size:
        raise RuntimeError(
            f"Frame extraction at {timestamp:.6f}s returned {len(result.stdout)} bytes, "
            f"expected {expected_size} ({width}x{height} BGR24)"
        )
    return np.frombuffer(result.stdout, dtype=np.uint8).reshape((height, width, 3))
