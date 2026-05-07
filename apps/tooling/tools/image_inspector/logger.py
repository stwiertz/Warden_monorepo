"""JSON-lines logger for Warden Image Inspector.

Appends structured entries to inspector_log.jsonl next to the inspected image.
"""

import json
import os
import sys
from datetime import datetime, timezone


def log_entry(image_path, entry_type, data):
    """Append a JSON-line entry to the log file.

    Args:
        image_path: Full path to the inspected image.
        entry_type: One of "color_pick", "roi", "hsv_filter".
        data: Dict with type-specific fields.
    """
    log_dir = os.path.dirname(os.path.abspath(image_path))
    log_file = os.path.join(log_dir, "inspector_log.jsonl")
    image_name = os.path.basename(image_path)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "image": image_name,
        "type": entry_type,
        "data": data,
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"Warning: could not write to log file {log_file}: {e}", file=sys.stderr)
