"""Warden Image Inspector — interactive HSV color picker, filter preview, and ROI selector.

Usage:
    python -m tools.image_inspector [path/to/image.png]
    python tools/image_inspector [path/to/image.png]

If no path is provided, a file dialog will open.
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Warden Image Inspector — HSV color picker, filter preview, and ROI selector"
    )
    parser.add_argument(
        "image",
        nargs="?",
        default=None,
        help="Path to a PNG image file (opens file dialog if omitted)",
    )
    args = parser.parse_args()

    image_path = args.image

    if image_path is not None and not os.path.isfile(image_path):
        print(f"Error: file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    # Import here so tkinter is only loaded after arg validation
    from .app import InspectorApp

    app = InspectorApp(image_path)
    app.mainloop()


if __name__ == "__main__":
    main()
