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


def get_video_duration(video_path):
    """Get video duration in seconds using ffprobe.

    Returns:
        float: Duration of the video stream in seconds.

    Raises:
        RuntimeError: If duration cannot be determined.
    """
    check_ffmpeg()
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    duration_str = info.get("format", {}).get("duration")
    if duration_str is None:
        raise RuntimeError(
            f"Could not determine duration for '{video_path}'. "
            "Ensure the file is a valid video."
        )
    return float(duration_str)


def get_keyframe_timestamps(video_path, scan_duration=30):
    """Get I-frame timestamps from the first N seconds of a video.

    Uses packet-level inspection (no decode) — orders of magnitude faster than
    frame-level scanning on long captures. The packet ``flags`` field contains
    ``K`` for keyframe packets.

    Args:
        video_path: Path to the input video file.
        scan_duration: How many seconds to scan from the start (default 30).

    Returns:
        list[float]: Sorted list of keyframe PTS timestamps in seconds.

    Raises:
        RuntimeError: If ffprobe returns no packet data.
    """
    check_ffmpeg()
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-read_intervals", f"%+{scan_duration}",
        "-show_packets",
        "-show_entries", "packet=pts_time,flags",
        "-of", "csv=p=0",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    timestamps = []
    saw_any_packet = False
    for line in result.stdout.splitlines():
        if not line:
            continue
        saw_any_packet = True
        parts = line.split(",")
        if len(parts) >= 2 and "K" in parts[1]:
            try:
                timestamps.append(float(parts[0]))
            except ValueError:
                pass
    if not saw_any_packet:
        raise RuntimeError(
            f"No packet data returned by ffprobe for '{video_path}'. "
            "Ensure the file is a valid video."
        )
    return sorted(timestamps)


def get_gop_interval(video_path, scan_duration=30):
    """Compute the median keyframe interval (GOP) for a video.

    Args:
        video_path: Path to the input video file.
        scan_duration: How many seconds to scan from the start (default 30).

    Returns:
        float: Median interval between consecutive keyframes in seconds.
               Returns 0.0 if fewer than 2 keyframes are found.
    """
    timestamps = get_keyframe_timestamps(video_path, scan_duration)
    if len(timestamps) < 2:
        return 0.0
    intervals = [
        timestamps[i + 1] - timestamps[i]
        for i in range(len(timestamps) - 1)
    ]
    intervals.sort()
    mid = len(intervals) // 2
    if len(intervals) % 2 == 0:
        return (intervals[mid - 1] + intervals[mid]) / 2
    return intervals[mid]


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


def extract_frame_at_timestamp_scaled(video_path, timestamp, target_height):
    """Extract a single frame at a timestamp, scaled to target height.

    Uses input seeking (-ss before -i) for fast seeking. Scales in the
    ffmpeg pipeline to avoid decoding full resolution.

    Args:
        video_path: Path to the input video file.
        timestamp: PTS timestamp in seconds (float).
        target_height: Desired output height in pixels.

    Returns:
        numpy array of shape (scaled_h, scaled_w, 3) in BGR color order.

    Raises:
        RuntimeError: If the extracted frame size doesn't match expected dimensions.
    """
    check_ffmpeg()
    src_w, src_h = get_video_info(video_path)
    scaled_w = round(src_w * target_height / src_h / 2) * 2
    scaled_h = target_height

    cmd = [
        "ffmpeg",
        "-v", "error",
        "-ss", f"{timestamp:.6f}",
        "-i", str(video_path),
        "-vf", f"scale={scaled_w}:{scaled_h}",
        "-frames:v", "1",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "pipe:1",
    ]

    result = subprocess.run(cmd, capture_output=True, check=True)
    expected_size = scaled_w * scaled_h * 3
    if len(result.stdout) != expected_size:
        raise RuntimeError(
            f"Frame extraction at {timestamp:.6f}s returned {len(result.stdout)} bytes, "
            f"expected {expected_size} ({scaled_w}x{scaled_h} BGR24)"
        )
    return np.frombuffer(result.stdout, dtype=np.uint8).reshape(
        (scaled_h, scaled_w, 3)
    )


def extract_frames_at_interval(video_path, target_height, start, end,
                                interval=2.0, iframe_timestamps=None,
                                snap_tolerance=0.5):
    """Yield (frame, timestamp) at regular intervals with I-frame snapping.

    Builds a list of target timestamps spaced by `interval` seconds. For each
    target, if an I-frame timestamp is within `snap_tolerance`, the I-frame
    timestamp is used instead (cheaper to seek to). Duplicates are removed.

    Args:
        video_path: Path to the input video file.
        target_height: Desired output height in pixels.
        start: Start of time range in seconds.
        end: End of time range in seconds.
        interval: Seconds between target frames (default 2.0).
        iframe_timestamps: Optional sorted list of known I-frame PTS times.
            If None, no snapping is performed.
        snap_tolerance: Max distance in seconds to snap to an I-frame (default 0.5).

    Yields:
        tuple: (frame, timestamp) where frame is BGR numpy array at target_height.
    """
    if end == float("inf"):
        raise ValueError(
            "extract_frames_at_interval requires a finite 'end' value. "
            "Pass an explicit end timestamp."
        )

    # Build target timestamp grid
    targets = []
    t = start
    while t <= end:
        targets.append(t)
        t += interval

    # Snap to nearest I-frame within tolerance
    if iframe_timestamps:
        snapped = []
        for target in targets:
            best = target
            best_dist = snap_tolerance
            for iframe_ts in iframe_timestamps:
                dist = abs(iframe_ts - target)
                if dist <= best_dist:
                    best = iframe_ts
                    best_dist = dist
            snapped.append(best)
        # Deduplicate while preserving order
        seen = set()
        targets = []
        for ts in snapped:
            if ts not in seen:
                seen.add(ts)
                targets.append(ts)

    for ts in targets:
        frame = extract_frame_at_timestamp_scaled(video_path, ts, target_height)
        yield frame, ts
