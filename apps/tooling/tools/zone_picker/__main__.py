"""Thin CLI entrypoint for the Unified Zone Picker (Story 9.12).

``python -m tools.zone_picker --hud-version {v1,v2} [--labeled-dir DIR]
[--zones-dir DIR] [--mode {hud,in_match,per_map}]``

Mirrors ``image_inspector/__main__.py``: argparse runs and bad args exit
non-zero **before** any tkinter import, so ``--help`` and arg-validation are
testable headless and a display is never required to reject bad input
(AC1/AC11 — pure logic must be importable without a display).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.common.labeled_dataset import default_labeled_dir

# apps/tooling/tools/zone_picker/__main__.py → apps/tooling is parents[2].
_TOOLING_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.zone_picker",
        description=(
            "Unified Zone Picker (Tool 10) — pick ROI+HSV zones in 3 modes "
            "over Tool 6's labeled PNG dataset; writes the 4 zone fragments "
            "map_config_emitter.py consumes."
        ),
    )
    parser.add_argument(
        "--hud-version",
        required=True,
        choices=["v1", "v2"],
        help="HUD generation this picking session calibrates (v1 or v2).",
    )
    parser.add_argument(
        "--labeled-dir",
        default=None,
        help="Tool 6's labeled-dataset root (default: apps/tooling/output/labeled).",
    )
    parser.add_argument(
        "--zones-dir",
        default=None,
        help=(
            "Where the 4 zone fragments are read/written "
            "(default: apps/tooling/output/zones/v<hud_version>/)."
        ),
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=["hud", "in_match", "per_map"],
        help="Optionally preselect a mode panel (else pick it in the UI).",
    )
    args = parser.parse_args(argv)

    labeled_dir = Path(args.labeled_dir) if args.labeled_dir else Path(default_labeled_dir())
    zones_dir = (
        Path(args.zones_dir)
        if args.zones_dir
        else _TOOLING_ROOT / "output" / "zones" / args.hud_version
    )

    if not labeled_dir.is_dir():
        print(f"Error: labeled-dir not found: {labeled_dir}", file=sys.stderr)
        return 1

    version_dir = labeled_dir / args.hud_version
    if not version_dir.is_dir():
        print(
            f"Error: no labeled frames for {args.hud_version}: {version_dir} "
            f"does not exist (run Tool 6 first).",
            file=sys.stderr,
        )
        return 1

    # Import the Tk shell ONLY after arg validation (image_inspector pattern) —
    # keeps --help / bad-arg paths display-free and import-light.
    from .app import ZonePickerApp

    app = ZonePickerApp(
        hud_version=args.hud_version,
        labeled_dir=labeled_dir,
        zones_dir=zones_dir,
        initial_mode=args.mode,
    )
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
