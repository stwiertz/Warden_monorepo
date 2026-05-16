"""Unified Zone Picker (Tool 10, Story 9.12).

Interactive Tk tool that picks ROI+HSV detection zones in three modes
(HUD-version detection / binary in-match detection / per-map weighted ID) over
Tool 6's labeled PNG dataset, with the recovered Tool 7 variance/heatmap signal
folded in as an in-tool preprocessing helper, writing the four zone fragments
the unchanged ``map_config_emitter.py`` (Story 9.9c) consumes.

Package layout (AC1 — pure logic isolated from Tk so AC11's no-Tk-in-tests
holds): ``fragments`` + ``variance`` are Tk-free and unit-tested; ``app`` +
``modes`` are the GUI shell and are never imported by the test suite.
"""
