"""
wardentooling.py — Warden pipeline TUI launcher.

Single entry point for all Warden tools. Presents an interactive
questionary-based menu, handles argument collection per tool, persists
the last run for quick re-execution.

Usage:
    python wardentooling.py
"""

import glob
import json
import os
import re
import sys
import subprocess

import questionary

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LAST_RUN_FILE = ".warden_last_run.json"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Exclude code/config dirs from directory browser — show only data dirs
_EXCLUDED_DIRS = {"tools", "utils", "config", "docs", "__pycache__"}


# ---------------------------------------------------------------------------
# Last-run persistence
# ---------------------------------------------------------------------------


def load_last_run() -> dict | None:
    """Return last-run state dict or None if missing / invalid."""
    path = os.path.join(PROJECT_ROOT, LAST_RUN_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_last_run(tool: str, label: str, args: list[str], video_path: str | None) -> None:
    """Persist last run metadata to LAST_RUN_FILE."""
    path = os.path.join(PROJECT_ROOT, LAST_RUN_FILE)
    data = {"tool": tool, "label": label, "args": args, "video_path": video_path}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_tool(args: list[str]) -> int:
    """Launch a tool via subprocess, streaming output to the terminal.

    Returns the exit code (0 = success). Callers should only persist
    last-run state when this returns 0.
    """
    result = subprocess.run([sys.executable] + args, cwd=PROJECT_ROOT)
    return result.returncode


# ---------------------------------------------------------------------------
# File selection helpers
# ---------------------------------------------------------------------------


def browse_video_file(prompt: str) -> str:
    """Prompt for an .mp4 file. Scans the project tree recursively so
    videos in subdirectories (e.g. source/) are discoverable.

    Loops until a valid, existing path is returned.
    """
    while True:
        mp4_files = sorted(
            glob.glob(os.path.join(PROJECT_ROOT, "**/*.mp4"), recursive=True)
        )
        choices = [os.path.relpath(f, PROJECT_ROOT) for f in mp4_files]
        manual_opt = "[ Enter path manually ]"
        choices.append(manual_opt)

        if mp4_files:
            selection = questionary.select(prompt, choices=choices).ask()
        else:
            selection = manual_opt

        if selection is None or selection == manual_opt:
            selection = questionary.text("Video file path:").ask()

        if selection and os.path.isfile(os.path.join(PROJECT_ROOT, selection)):
            return selection
        print(f"  Path not found: {selection!r} — please try again.")


def browse_image_file(prompt: str) -> str | None:
    """Prompt for an optional image file. Scans project root only (non-recursive)
    to avoid slow traversal of large output/ directories.

    Accepts common image formats. Returns None if user skips.
    """
    image_exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff")
    img_files = []
    for ext in image_exts:
        img_files.extend(glob.glob(os.path.join(PROJECT_ROOT, ext)))
    img_files = sorted(img_files)

    choices = [os.path.relpath(f, PROJECT_ROOT) for f in img_files]
    skip_opt = "[ Skip — launch without image ]"
    manual_opt = "[ Enter path manually ]"
    choices += [manual_opt, skip_opt]

    while True:
        selection = questionary.select(prompt, choices=choices).ask()
        if selection is None or selection == skip_opt:
            return None
        if selection == manual_opt:
            selection = questionary.text("Image file path (or blank to skip):").ask()
            if not selection:
                return None
        if selection and os.path.isfile(os.path.join(PROJECT_ROOT, selection)):
            return selection
        print(f"  Path not found: {selection!r} — please try again.")


def browse_directory(prompt: str) -> str:
    """Prompt for a directory. Shows only non-code subdirs of project root
    (excludes dirs starting with '.' or '_' and known code dirs).

    Loops until a valid, existing directory is returned.
    """
    while True:
        try:
            subdirs = sorted(
                e.name
                for e in os.scandir(PROJECT_ROOT)
                if e.is_dir()
                and not e.name.startswith(".")
                and not e.name.startswith("_")
                and e.name not in _EXCLUDED_DIRS
            )
        except OSError:
            subdirs = []

        manual_opt = "[ Enter path manually ]"
        choices = subdirs + [manual_opt]

        if subdirs:
            selection = questionary.select(prompt, choices=choices).ask()
        else:
            selection = manual_opt

        if selection is None or selection == manual_opt:
            selection = questionary.text("Directory path:").ask()

        if selection and os.path.isdir(os.path.join(PROJECT_ROOT, selection)):
            return selection
        print(f"  Directory not found: {selection!r} — please try again.")


# ---------------------------------------------------------------------------
# Tool 1 — game_detector
# ---------------------------------------------------------------------------


def flow_tool1() -> tuple[list[str], str | None]:
    """Collect arguments for game_detector.py.

    Returns (args_list, video_path).
    """
    video_path = browse_video_file("Select video file for Tool 1 — Extract Rounds:")
    args = ["tools/game_detector.py", video_path]

    output_dir = questionary.text("Output directory (-o)  [blank = default]:").ask()
    if output_dir:
        args += ["-o", output_dir]

    use_profile = questionary.confirm(
        "Enable --profile (performance profiling)?", default=False
    ).ask()
    if use_profile:
        args.append("--profile")

    return args, video_path


# ---------------------------------------------------------------------------
# Tool 2 — frame_labeler
# ---------------------------------------------------------------------------


def flow_tool2() -> tuple[list[str], str | None]:
    """Collect arguments for frame_labeler.py.

    Returns (args_list, None) — no video_path for this tool.
    """
    source_dir = browse_directory(
        "Select Tool 1 output folder (source for frame labeler):"
    )
    args = ["tools/frame_labeler.py", source_dir]

    output_dir = questionary.text("Output directory (-o)  [blank = default]:").ask()
    if output_dir:
        args += ["-o", output_dir]

    return args, None


# ---------------------------------------------------------------------------
# Tool 3 — map_config_generator
# ---------------------------------------------------------------------------


def flow_tool3() -> tuple[list[str], str | None]:
    """Collect arguments for map_config_generator.py.

    Returns (args_list, video_path_or_None).
    Returns ([], None) if user cancels at the mode selection prompt.
    """
    mode = questionary.select(
        "Tool 3 — input mode:",
        choices=[
            "From image directory (--images)",
            "From video files (--video)",
        ],
    ).ask()

    if mode is None:
        return [], None  # user cancelled at mode prompt

    args = ["tools/map_config_generator.py"]
    video_path = None

    if mode == "From image directory (--images)":
        images_dir = browse_directory("Select image directory:")
        args += ["--images", images_dir]
    else:
        # --video MAP PATH [--video MAP2 PATH2 ...]
        first = True
        while True:
            prompt = "Map name for first video:" if first else "Map name for next video:"
            first = False
            map_name = questionary.text(prompt).ask()
            if not map_name:
                # Blank/cancelled map name — require at least one entry
                if video_path is None:
                    print("  At least one map is required.")
                    continue
                break
            vid = browse_video_file(f"Video file for map '{map_name}':")
            args += ["--video", map_name, vid]
            if video_path is None:
                video_path = vid
            add_more = questionary.confirm("Add another map?", default=False).ask()
            if not add_more:
                break

    use_preview = questionary.confirm(
        "Enable --preview (show image previews)?", default=False
    ).ask()
    if use_preview:
        args.append("--preview")

    output_dir = questionary.text("Output directory (-o)  [blank = default]:").ask()
    if output_dir:
        args += ["-o", output_dir]

    return args, video_path


# ---------------------------------------------------------------------------
# Dev tool flows
# ---------------------------------------------------------------------------


def flow_dev_roi_debugger() -> tuple[list[str], str | None]:
    """Collect arguments for bsd_roi_debugger.py."""
    video_path = browse_video_file("Select video file for ROI Debugger:")
    args = ["tools/bsd_roi_debugger.py", video_path]

    # --range with N:N format validation
    while True:
        range_val = questionary.text("Time range (--range N:N):", default="0:15").ask()
        if re.match(r"^\d+:\d+$", range_val or ""):
            args += ["--range", range_val]
            break
        print("  Invalid format — enter as N:N (e.g. 0:15)")

    threshold = questionary.text("Threshold (--threshold)  [blank = default]:").ask()
    if threshold:
        args += ["--threshold", threshold]

    output_dir = questionary.text("Output directory (-o)  [blank = default]:").ask()
    if output_dir:
        args += ["-o", output_dir]

    return args, video_path


def flow_dev_points_detector() -> tuple[list[str], str | None]:
    """Collect arguments for points_state_detector.py."""
    video_path = browse_video_file("Select video file for Points State Detector:")
    args = ["tools/points_state_detector.py", video_path]

    roi = questionary.text(
        "ROI name (--roi)  [blank = default 'points']:", default="points"
    ).ask()
    if roi and roi != "points":
        args += ["--roi", roi]

    use_profile = questionary.confirm("Enable --profile?", default=False).ask()
    if use_profile:
        args.append("--profile")

    return args, video_path


def flow_dev_image_inspector() -> tuple[list[str], str | None]:
    """Collect arguments for image_inspector (module invocation).

    Invokes as: python -m tools.image_inspector [image]
    """
    args = ["-m", "tools.image_inspector"]
    image_path = browse_image_file("Select image to open (optional):")
    if image_path:
        args.append(image_path)
    return args, None


# ---------------------------------------------------------------------------
# Dev submenu
# ---------------------------------------------------------------------------


def menu_dev() -> None:
    """Dev/Diagnostics submenu — loops until Back."""
    while True:
        choice = questionary.select(
            "Dev Tools:",
            choices=[
                "Image Inspector",
                "ROI Debugger",
                "Points State Detector",
                "← Back",
            ],
        ).ask()

        if choice is None or choice == "← Back":
            return

        if choice == "Image Inspector":
            args, _ = flow_dev_image_inspector()
            run_tool(args)
        elif choice == "ROI Debugger":
            args, _ = flow_dev_roi_debugger()
            run_tool(args)
        elif choice == "Points State Detector":
            args, _ = flow_dev_points_detector()
            run_tool(args)


# ---------------------------------------------------------------------------
# Main menu + last-run offer
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "game_detector":        ("Tool 1 — Extract Rounds",     flow_tool1),
    "frame_labeler":        ("Tool 2 — Label Frames",        flow_tool2),
    "map_config_generator": ("Tool 3 — Generate Map Config", flow_tool3),
}


def _reprompt_source(
    tool_key: str, last_args: list[str]
) -> tuple[list[str], str | None]:
    """Re-prompt only the source path for 'Run on new source', keeping all
    other flags from the previous run intact.

    Tool 3 is too structurally complex for partial re-prompt; runs full flow.
    """
    if tool_key == "game_detector":
        new_video = browse_video_file("Select new video file:")
        # last_args layout: ["tools/game_detector.py", <video>, ...]
        new_args = [last_args[0], new_video] + last_args[2:]
        return new_args, new_video
    elif tool_key == "frame_labeler":
        new_source = browse_directory("Select new source directory:")
        # last_args layout: ["tools/frame_labeler.py", <source_dir>, ...]
        new_args = [last_args[0], new_source] + last_args[2:]
        return new_args, None
    else:
        # map_config_generator: arg structure varies too much; run full flow
        return flow_tool3()


def _offer_last_run(last: dict) -> None:
    """Offer to re-run the previous tool. Handles run/new-source/skip."""
    label = last.get("label", last.get("tool", "previous tool"))
    choice = questionary.select(
        f"Last run: {label}",
        choices=["Run on new source", "Run with same args", "Skip"],
    ).ask()

    if choice is None or choice == "Skip":
        return

    exe_name = os.path.basename(sys.executable)

    if choice == "Run with same args":
        saved_args = last.get("args")
        if not saved_args:
            print("  No args found in last-run state. Skipping.")
            return
        run_tool(saved_args)  # last-run state unchanged; args are identical
        return

    if choice == "Run on new source":
        tool_key = last.get("tool")
        if tool_key not in _TOOL_MAP:
            print(f"  Unknown tool '{tool_key}' — cannot re-prompt. Skipping.")
            return
        _label, _ = _TOOL_MAP[tool_key]
        saved_args = last.get("args") or []
        args, video_path = _reprompt_source(tool_key, saved_args)
        if not args:
            return  # user cancelled (e.g. flow_tool3 returned empty)
        confirmed = questionary.confirm(
            f"Run: {exe_name} {' '.join(args)}?", default=True
        ).ask()
        if confirmed:
            returncode = run_tool(args)
            if returncode == 0:
                save_last_run(tool_key, _label, args, video_path)


def menu_main() -> None:
    """Main menu loop — runs until Quit."""
    last = load_last_run()
    if last:
        _offer_last_run(last)

    exe_name = os.path.basename(sys.executable)
    choices_main = [
        "Tool 1 — Extract Rounds",
        "Tool 2 — Label Frames",
        "Tool 3 — Generate Map Config",
        "Dev Tools",
        "Quit",
    ]

    while True:
        choice = questionary.select("Warden Tooling:", choices=choices_main).ask()

        if choice is None or choice == "Quit":
            return

        if choice == "Tool 1 — Extract Rounds":
            args, video_path = flow_tool1()
            if not args:
                continue
            confirmed = questionary.confirm(
                f"Run: {exe_name} {' '.join(args)}?", default=True
            ).ask()
            if confirmed:
                returncode = run_tool(args)
                if returncode == 0:
                    save_last_run("game_detector", "Tool 1 — Extract Rounds", args, video_path)

        elif choice == "Tool 2 — Label Frames":
            args, video_path = flow_tool2()
            if not args:
                continue
            confirmed = questionary.confirm(
                f"Run: {exe_name} {' '.join(args)}?", default=True
            ).ask()
            if confirmed:
                returncode = run_tool(args)
                if returncode == 0:
                    save_last_run("frame_labeler", "Tool 2 — Label Frames", args, video_path)

        elif choice == "Tool 3 — Generate Map Config":
            args, video_path = flow_tool3()
            if not args:
                continue
            confirmed = questionary.confirm(
                f"Run: {exe_name} {' '.join(args)}?", default=True
            ).ask()
            if confirmed:
                returncode = run_tool(args)
                if returncode == 0:
                    save_last_run(
                        "map_config_generator",
                        "Tool 3 — Generate Map Config",
                        args,
                        video_path,
                    )

        elif choice == "Dev Tools":
            menu_dev()


def main() -> None:
    """Entry point — wraps everything in KeyboardInterrupt handler."""
    try:
        menu_main()
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
