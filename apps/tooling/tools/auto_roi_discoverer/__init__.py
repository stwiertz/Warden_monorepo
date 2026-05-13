"""Tool 8 — Auto ROI/HSV Discoverer.

Interactive Tk review tool that consumes Tool 7's per-``(version, class)``
overlay-stack statistics (``stats.npz`` + ``overlay_stacks_summary.json``), auto-
suggests / scores / validates game-state ROI candidates over the four target
classes (``lobby``, ``in_match`` [pooled], ``score``, ``transition`` [kept for
rejection]), supports manual zone / exclusion editing, and exports a hand-merge
config fragment + a report + per-class previews — it never edits ``config/config.yaml``.

The pure logic (``loader``, ``discoverer``, ``validator``, ``exclusions``,
``export``, ``model``) is importable and unit-testable without Tk; the GUI lives
entirely in ``app`` / ``__main__``.
"""
