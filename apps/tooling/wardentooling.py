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
import sys
import subprocess

import questionary

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LAST_RUN_FILE = ".warden_last_run.json"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


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


# browse_directory() — REMOVED (Story 9.11: its sole caller was the retired
# Tool 2 flow; no other references remained).


# ---------------------------------------------------------------------------
# Tool 1 (round extractor) + Tool 2 (frame labeler) — REMOVED (Story 9.11:
# retired legacy tooling; black-screen detection is replaced by
# `in_match_detection` zones, Tool 6 supersedes the old frame labeler).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tool 3 — map_config_emitter
# ---------------------------------------------------------------------------


def flow_tool3() -> tuple[list[str], str | None]:
    """Collect arguments for map_config_emitter.py.

    Reads zone fragments from a zones directory (written by zone_picker, Story
    9.12) and emits a unified map_config.<hud_version>.json. No config.yaml
    input. Pure fragment-driven — no frame input needed.

    Returns (args_list, None) — no video_path for this tool.
    """
    args = ["tools/map_config_emitter.py"]

    zones_parent = os.path.join(PROJECT_ROOT, "output", "zones")
    # `_display` is repo-root-relative (clear for the user). `_value` is what
    # actually gets passed to the emitter subprocess, which runs with
    # cwd=PROJECT_ROOT (=apps/tooling/), so it must be relative to that.
    zones_default_display = "apps/tooling/output/zones/"
    zones_default_value = os.path.join("output", "zones")
    zones_dir = questionary.text(
        f"Zones directory (--zones-dir)  [blank = pick from {zones_default_display}]:"
    ).ask()
    if zones_dir:
        zones_dir = zones_dir.strip()
    else:
        # Blank: offer a picker over subdirectories of the conventional parent.
        # No auto-select. If the parent doesn't exist, fall through with the
        # default value so the emitter's clean error surfaces ("no fragment
        # files at <path>"); this is the documented pre-9.12 behavior.
        try:
            subdirs = sorted(
                e.name
                for e in os.scandir(zones_parent)
                if e.is_dir() and not e.name.startswith(".")
            )
        except OSError:
            subdirs = []

        if subdirs:
            picked = questionary.select(
                "Zone fragment directory:",
                choices=subdirs,
            ).ask()
            if picked:
                zones_dir = os.path.join("output", "zones", picked)
            else:
                zones_dir = zones_default_value
        else:
            zones_dir = zones_default_value

    args += ["--zones-dir", zones_dir]

    output_dir = questionary.text(
        "Output directory (--output-dir)  [blank = apps/tooling/output/map_configs/]:"
    ).ask()
    if output_dir:
        args += ["--output-dir", output_dir.strip()]

    return args, None


# ---------------------------------------------------------------------------
# Tool 4 — REMOVED (was: hash_validator; deleted along with pHash codepath
# per Story 9.9a Scope Adjustment #2, 2026-05-15 — ROI+HSV is the sole
# detection method, pHash never shipped).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tool 5 (round analyzer) — REMOVED (Story 9.11: retired legacy tooling;
# Story 9.2 cancelled, HUD 2.0 footage breaks its legacy ROIs).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tool 6 — video_timeline_labeler
# ---------------------------------------------------------------------------


def flow_tool6() -> tuple[list[str], str | None]:
    """Collect arguments for video_timeline_labeler.py.

    Returns (args_list, video_path). Returns ([], None) if the user cancels
    any prompt (Ctrl-C from questionary returns None; cancel from
    browse_video_file returns None).
    """
    video_path = browse_video_file(
        "Select video file for Tool 6 — Label Frames from Video Timeline:"
    )
    if not video_path:
        return [], None
    args = ["tools/video_timeline_labeler.py", video_path]

    output_dir = questionary.text("Output directory (-o)  [blank = default]:").ask()
    if output_dir:
        args += ["-o", output_dir]

    snap_policy = questionary.select(
        "Snap policy (--snap):",
        choices=["nearest", "prior", "after"],
    ).ask()
    # questionary returns None on Ctrl-C — treat as cancel so the user
    # doesn't silently proceed with the default policy.
    if snap_policy is None:
        return [], None
    if snap_policy != "nearest":
        args += ["--snap", snap_policy]

    return args, video_path


# ---------------------------------------------------------------------------
# Tool 7 (overlay-stack analyzer) + Tool 8 (auto ROI discoverer) — REMOVED
# (Story 9.11: retired legacy tooling; the variance/heatmap signal folds into
# zone_picker (9.12) and the auto-suggest ROI layer is superseded by the
# manual picker).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tool 9 — roi_detection_tester (single-file headless tool)
# ---------------------------------------------------------------------------


def flow_tool9() -> tuple[list[str], str | None]:
    """Collect arguments for roi_detection_tester.py.

    Reads an emitted map_config.<hud_version>.json (the Story 9.9c unified
    schema, written by map_config_emitter / Tool 3) and replays Tool 6's
    labeled PNG dataset through it, reporting three classifiers (HUD-version,
    binary in_match, per-map ID). Returns ([], None) if the user Ctrl-C's any
    prompt (questionary returns None on interrupt).
    """
    args = ["tools/roi_detection_tester.py"]

    def _is_pos_int(text: str) -> bool:
        return text.isascii() and text.isdigit() and int(text) > 0

    def _is_unit_float(text: str) -> bool:
        try:
            return 0.0 <= float(text) <= 1.0
        except ValueError:
            return False

    configs_parent = os.path.join(PROJECT_ROOT, "output", "map_configs")
    config_path = questionary.text(
        "Map config (--config)  [blank = pick newest map_config.*.json from "
        "apps/tooling/output/map_configs/]:"
    ).ask()
    if config_path is None:
        return [], None
    config_path = config_path.strip()
    if config_path:
        args += ["--config", config_path]
    else:
        # Blank: offer a picker over map_config.*.json files in the conventional
        # parent. No auto-select. If none exist, fall through WITHOUT --config
        # so roi_detection_tester's own newest-config default / clean error
        # surfaces (mirrors flow_tool3's blank-picker-over-default pattern).
        try:
            cfg_files = sorted(
                e.name
                for e in os.scandir(configs_parent)
                if e.is_file()
                and e.name.startswith("map_config.")
                and e.name.endswith(".json")
            )
        except OSError:
            cfg_files = []
        if cfg_files:
            picked = questionary.select(
                "Map config file:",
                choices=cfg_files,
            ).ask()
            if picked is None:
                return [], None
            if picked:
                args += ["--config", os.path.join("output", "map_configs", picked)]

    labeled_dir = questionary.text(
        "Labeled dataset directory (--labeled)  [blank = output/labeled]:"
    ).ask()
    if labeled_dir is None:
        return [], None
    labeled_dir = labeled_dir.strip()
    if labeled_dir:
        args += ["--labeled", labeled_dir]

    output_dir = questionary.text(
        "Report output directory (--output)  [blank = output/roi_detection_tests]:"
    ).ask()
    if output_dir is None:
        return [], None
    output_dir = output_dir.strip()
    if output_dir:
        args += ["--output", output_dir]

    while True:
        limit = questionary.text(
            "Cap frames per class (--limit)  [blank = no cap]:"
        ).ask()
        if limit is None:
            return [], None
        limit = limit.strip()
        if not limit:
            break
        if _is_pos_int(limit):
            args += ["--limit", limit]
            break
        print("  Invalid — enter a positive integer (or blank for no cap).")

    for flag, prompt in (
        ("--hud-version-threshold",
         "HUD-version threshold (--hud-version-threshold)  [blank = 0.5]:"),
        ("--in-match-threshold",
         "in_match threshold (--in-match-threshold)  [blank = 0.5]:"),
        ("--map-threshold",
         "Per-map threshold (--map-threshold)  [blank = config's "
         "identification_threshold]:"),
    ):
        while True:
            val = questionary.text(prompt).ask()
            if val is None:
                return [], None
            val = val.strip()
            if not val:
                break
            if _is_unit_float(val):
                args += [flag, val]
                break
            print("  Invalid — enter a number in [0.0, 1.0] (or blank).")

    save_csv = questionary.confirm(
        "Save per-frame predictions CSV too (--save-frame-predictions)?", default=False
    ).ask()
    if save_csv is None:
        return [], None
    if save_csv:
        args.append("--save-frame-predictions")

    return args, None


# ---------------------------------------------------------------------------
# Tool 10 — zone_picker (interactive Tk package; -m invocation)
# ---------------------------------------------------------------------------


def flow_zone_picker() -> tuple[list[str], str | None]:
    """Collect arguments for the Unified Zone Picker (Story 9.12).

    Package invocation: ``python -m tools.zone_picker --hud-version {v1,v2}``
    (mirrors flow_dev_image_inspector's ``-m`` pattern; run_tool already does
    ``[sys.executable] + args`` so no run_tool change is needed). Returns
    ([], None) if the user Ctrl-C's any prompt (questionary returns None).
    """
    hud_version = questionary.select(
        "HUD version this picking session calibrates (--hud-version):",
        choices=["v1", "v2"],
    ).ask()
    if hud_version is None:
        return [], None
    args = ["-m", "tools.zone_picker", "--hud-version", hud_version]

    labeled_dir = questionary.text(
        "Labeled dataset root (--labeled-dir)  [blank = output/labeled]:"
    ).ask()
    if labeled_dir is None:
        return [], None
    labeled_dir = labeled_dir.strip()
    if labeled_dir:
        args += ["--labeled-dir", labeled_dir]

    zones_dir = questionary.text(
        "Zone-fragment dir (--zones-dir)  [blank = output/zones/v<hud>]:"
    ).ask()
    if zones_dir is None:
        return [], None
    zones_dir = zones_dir.strip()
    if zones_dir:
        args += ["--zones-dir", zones_dir]

    mode = questionary.select(
        "Preselect a mode panel (--mode):",
        choices=["(let me pick in the UI)", "hud", "in_match", "per_map"],
    ).ask()
    if mode is None:
        return [], None
    if mode != "(let me pick in the UI)":
        args += ["--mode", mode]

    return args, None


# ---------------------------------------------------------------------------
# Dev tool flows
# ---------------------------------------------------------------------------


# Dev ROI Debugger + Dev Points State Detector flows — REMOVED
# (Story 9.11: retired legacy tooling).


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
                "← Back",
            ],
        ).ask()

        if choice is None or choice == "← Back":
            return

        if choice == "Image Inspector":
            args, _ = flow_dev_image_inspector()
            run_tool(args)


# ---------------------------------------------------------------------------
# Main menu + last-run offer
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    # Tools 1, 2, 4, 5, 7, 8 removed (Tool 4 per Story 9.9a Scope Adjustment
    # #2; Tools 1/2/5/7/8 per Story 9.11). Surviving numbers are intentionally
    # left non-contiguous — Tool 9's key/label/numbering is preserved to avoid
    # churning save_last_run state.
    "map_config_emitter":     ("Tool 3 — Emit Map Config",                      flow_tool3),
    "video_timeline_labeler": ("Tool 6 — Label Frames from Video Timeline",     flow_tool6),
    "roi_detection_tester":   ("Tool 9 — Test ROI Detection on Labeled Frames", flow_tool9),
    "zone_picker":            ("Tool 10 — Unified Zone Picker",                 flow_zone_picker),
}


def _reprompt_source(
    tool_key: str, last_args: list[str]
) -> tuple[list[str], str | None]:
    """Re-prompt only the source path for 'Run on new source', keeping all
    other flags from the previous run intact.

    Tool 3 is too structurally complex for partial re-prompt; runs full flow.
    """
    if tool_key == "video_timeline_labeler":
        new_video = browse_video_file("Select new video file:")
        if not new_video:
            # User cancelled the picker — bail to the main menu instead of
            # injecting the literal "None" into the args list.
            return [], None
        # last_args layout: ["tools/video_timeline_labeler.py", <video>, ...]
        new_args = [last_args[0], new_video] + last_args[2:]
        return new_args, new_video
    elif tool_key == "roi_detection_tester":
        # Directory-driven (consumes a zones fragment + the labeled dataset) —
        # re-run the full flow.
        return flow_tool9()
    elif tool_key == "zone_picker":
        # Option-driven interactive tool — re-run the full flow.
        return flow_zone_picker()
    else:
        # map_config_emitter: directory-driven re-run of the full flow.
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
    # Numbering is intentionally non-contiguous: Tools 1/2/4/5/7/8 were retired
    # (Story 9.11; Tool 4 earlier per 9.9a) — surviving tools keep their
    # original numbers/keys so save_last_run state stays valid.
    choices_main = [
        "Tool 3 — Emit Map Config",
        "Tool 6 — Label Frames from Video Timeline",
        "Tool 9 — Test ROI Detection on Labeled Frames",
        "Tool 10 — Unified Zone Picker",
        "Dev Tools",
        "Quit",
    ]

    while True:
        choice = questionary.select("Warden Tooling:", choices=choices_main).ask()

        if choice is None or choice == "Quit":
            return

        if choice == "Tool 3 — Emit Map Config":
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
                        "map_config_emitter",
                        "Tool 3 — Emit Map Config",
                        args,
                        video_path,
                    )

        elif choice == "Tool 6 — Label Frames from Video Timeline":
            args, video_path = flow_tool6()
            if not args:
                continue
            confirmed = questionary.confirm(
                f"Run: {exe_name} {' '.join(args)}?", default=True
            ).ask()
            if confirmed:
                returncode = run_tool(args)
                if returncode == 0:
                    save_last_run(
                        "video_timeline_labeler",
                        "Tool 6 — Label Frames from Video Timeline",
                        args,
                        video_path,
                    )

        elif choice == "Tool 9 — Test ROI Detection on Labeled Frames":
            args, video_path = flow_tool9()
            if not args:
                continue
            confirmed = questionary.confirm(
                f"Run: {exe_name} {' '.join(args)}?", default=True
            ).ask()
            if confirmed:
                returncode = run_tool(args)
                if returncode == 0:
                    save_last_run(
                        "roi_detection_tester",
                        "Tool 9 — Test ROI Detection on Labeled Frames",
                        args,
                        video_path,
                    )

        elif choice == "Tool 10 — Unified Zone Picker":
            args, video_path = flow_zone_picker()
            if not args:
                continue
            confirmed = questionary.confirm(
                f"Run: {exe_name} {' '.join(args)}?", default=True
            ).ask()
            if confirmed:
                returncode = run_tool(args)
                if returncode == 0:
                    save_last_run(
                        "zone_picker",
                        "Tool 10 — Unified Zone Picker",
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
