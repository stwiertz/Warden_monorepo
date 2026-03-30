"""Entry point for the Minimap Zone Selector tool.

Usage:
    python -m tools.minimap_zone_selector --labeled <dir> [--config <path>]
"""

import argparse
import sys

from .app import MinimapZoneSelectorApp


def main():
    parser = argparse.ArgumentParser(
        description="Minimap Zone Selector — define HSV zones for map identification."
    )
    parser.add_argument(
        "--labeled",
        required=True,
        help="Directory containing labeled map images (<dir>/<map_label>/*.png).",
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config.yaml (default: config/config.yaml).",
    )
    args = parser.parse_args()

    app = MinimapZoneSelectorApp(args.labeled, args.config)
    app.mainloop()


if __name__ == "__main__":
    main()
