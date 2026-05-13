"""Entry point for the Auto ROI/HSV Discoverer (Tool 8).

Usage:
    python -m tools.auto_roi_discoverer [--input INPUT_DIR] [--config CONFIG_PATH]
        [--exclusions EXCLUSIONS_PATH]

(From ``apps/tooling/``: ``python -m tools.auto_roi_discoverer``.)

argparse → validate args → heavy-load Tool 7's output (so a bad/old/missing input
fails cleanly *before* Tk loads) → import the Tk app lazily → ``mainloop()``.
"""

import argparse
import os
import sys

# Lift ``apps/tooling/`` onto sys.path so ``utils.*`` / ``tools.*`` resolve when run
# directly — consistent with the other tools' entry points. (``__file__`` lives at
# ``apps/tooling/tools/auto_roi_discoverer/__main__.py`` → ``../..`` is ``apps/tooling``.)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from .loader import (  # noqa: E402
    DEFAULT_EXCLUSIONS_PATH,
    LoaderError,
    default_input_dir,
    load_legacy_rois,
    load_overlay_stacks,
)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.auto_roi_discoverer",
        description="Tool 8 - Auto ROI/HSV Discoverer: suggest / score / validate "
        "game-state ROI candidates from Tool 7's overlay-stack statistics.",
    )
    parser.add_argument(
        "--input", default=None,
        help="Tool 7's output root (default: apps/tooling/output/overlay_stacks - "
        "Tool 7's default --output).",
    )
    parser.add_argument(
        "--config", default="config/config.yaml",
        help="Path to config/config.yaml - READ-ONLY, used only to draw the legacy "
        "HUD-1.0 ROIs as a faded reference overlay; never written. (default: config/config.yaml)",
    )
    parser.add_argument(
        "--exclusions", default=None,
        help="Path to an exclusions.yaml (per-version -> per-class named mask rects). "
        "Default: apps/tooling/output/auto_rois/exclusions.yaml if it exists, else none.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    input_dir = os.path.abspath(args.input) if args.input else default_input_dir()
    config_path = args.config
    exclusions_path = args.exclusions
    if exclusions_path is None and os.path.isfile(DEFAULT_EXCLUSIONS_PATH):
        exclusions_path = DEFAULT_EXCLUSIONS_PATH

    # Heavy load happens here so a bad / old / missing Tool 7 output fails cleanly
    # to stderr (no traceback) and exits non-zero BEFORE Tk loads (AC3).
    try:
        loaded = load_overlay_stacks(input_dir)
    except LoaderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    legacy_rois = load_legacy_rois(config_path)  # tolerant — warns + returns None on trouble

    # Import Tk only after the load succeeds (so a bad arg never pays the Tk cost).
    from .app import AutoRoiDiscovererApp  # noqa: E402

    app = AutoRoiDiscovererApp(
        loaded=loaded,
        legacy_rois=legacy_rois,
        exclusions_path=exclusions_path,
    )
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
