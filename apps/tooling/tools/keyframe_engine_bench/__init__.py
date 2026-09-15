"""Tool 12 — Keyframe Engine Bench (Story 12.1).

PC proof-of-concept for the engine-first pivot: decode only a video's keyframes
(FFmpeg ``-skip_frame nokey``, RAM pipe, no disk write of decoded frames) and
evaluate every ``map_config`` HSV rule in ONE GPU mega-shader, reporting
measured ms/keyframe and accuracy parity against the Tool 9 CPU baseline.

Layout (AC1/AC3 — the GL context is isolated behind a ``run()``-shaped seam):

* ``lut``      — PURE: rule packing + result decoding. No GL.
* ``frames``   — PURE: the AC8b frame-source seam (labeled PNGs | video keyframes).
* ``phases``   — PURE: phase state machine, doubt resolution, circular buffer.
* ``scoring``  — PURE: Tool 9's three per-classifier formulas (AC13).
* ``shader``   — GL-ISOLATED: context, program, FBO. The only module importing moderngl.
* ``keyframe_engine_bench.frag`` — GLSL authored in the ES-3.0-compatible subset (AC6/E2).

A PC number is NEVER a mobile number (AC14/E6): everything this package reports
is feasibility / relative speedup. It does not bind PERF-002 or PERF-010.
"""
