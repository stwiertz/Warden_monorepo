"""Formatting utilities for the Warden pipeline."""


def format_timestamp(seconds):
    """Format seconds as MMmSSs for filenames (e.g. 05m23s)."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}m{secs:02d}s"
