"""GL-ISOLATED module — context, program, FBO (AC3, AC4, AC6).

This is the seam. ``architecture.md:1148`` prescribes "stateless pure functions
(np in -> np out)" but a GL context is stateful; E7 names that friction. The
resolution: EVERY other module in this package is GL-free and unit-testable
without a context, and all statefulness is quarantined behind this file's
:class:`MegaShader`, which is only ever constructed inside ``run()``.

Nothing here is imported at test time — AC16 forbids a GL context in the suite.
``moderngl`` is imported lazily inside :class:`MegaShader` so that merely
importing this module (e.g. for :func:`build_source` or :func:`validate_glsl`,
both pure) costs no GL and works on a box with no driver at all.
"""

import os
import shutil
import subprocess

import numpy as np

from .lut import MAX_RULES

_FRAG_FILENAME = "keyframe_engine_bench.frag"


class GlslangNotFoundError(RuntimeError):
    """``glslangValidator`` is not installed / not locatable.

    Distinct from a shader that fails the gate: "the gate did not run" and "the
    gate ran and rejected the shader" are opposite facts, and collapsing them
    into one ``[FAIL]`` line lets a CI box with no glslang report the same thing
    as a genuinely non-conformant shader.
    """

# One body, two dialects, swapped on the #version line ONLY (AC6/E2). This is
# what makes Story 12.2 a port rather than a rewrite.
VERSION_ES = "#version 300 es"
VERSION_DESKTOP = "#version 330 core"

# The vertex stage is a fullscreen triangle over the 150x1 target: no attributes,
# no buffers, gl_VertexID only (ES 3.00 has gl_VertexID; ES 2.0 did not).
# Authored in the same subset -- note `2.0`/`4.0`/`1.0` are explicit floats and
# the int->float conversions are explicit `float(...)` casts.
_VERT_BODY = """
precision highp float;
precision highp int;

void main() {
    // (-1,-1), (3,-1), (-1,3) -- covers the viewport with a single triangle.
    float x = (gl_VertexID == 1) ? 3.0 : -1.0;
    float y = (gl_VertexID == 2) ? 3.0 : -1.0;
    gl_Position = vec4(x, y, 0.0, 1.0);
}
"""


def _frag_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), _FRAG_FILENAME)


def read_frag_body() -> str:
    """The shared GLSL body, verbatim from disk (no ``#version`` line)."""
    with open(_frag_path(), "r", encoding="utf-8") as fh:
        return fh.read()


def build_source(body: str, version: str) -> str:
    """Prepend a ``#version`` line to a shared body. PURE.

    The whole ES-3.0 story rests on this being the ONLY difference between what
    runs on desktop and what will run on Adreno.
    """
    return f"{version}\n{body}"


def find_glslang() -> str | None:
    """Locate ``glslangValidator``. PATH first, then ``$GLSLANG_VALIDATOR``."""
    env = os.environ.get("GLSLANG_VALIDATOR")
    if env and os.path.isfile(env):
        return env
    return shutil.which("glslangValidator") or shutil.which("glslang")


def validate_glsl(source: str, stage: str, workdir: str) -> tuple[bool, str]:
    """Compile ``source`` through ``glslangValidator``. Returns ``(ok, output)``.

    NOTE — deviation from AC6's literal command, which prescribes
    ``glslangValidator -G -S frag``. ``-G`` requests SPIR-V-for-OpenGL codegen and
    REJECTS ``#version 300 es`` outright ("ES shaders for SPIR-V require version
    310 or higher"), so the prescribed flag cannot validate the ES 3.00 dialect
    that E2 mandates. Dropping ``-G`` runs glslang's GLSL/ESSL front-end, which
    is the part that enforces the subset. Verified live: this gate rejects
    ``float x = 1;`` under ``#version 300 es`` and accepts it under
    ``#version 330 core`` -- i.e. it genuinely catches the #1 silent killer,
    which the ``-G`` form could not even reach.

    Raises:
        GlslangNotFoundError: if the validator cannot be located. This is NOT
            reported as ``(False, ...)`` — a missing gate and a failed gate are
            different outcomes and callers must be able to tell them apart.
    """
    exe = find_glslang()
    if exe is None:
        raise GlslangNotFoundError(
            "glslangValidator not found. Install it or set $GLSLANG_VALIDATOR. "
            "Desktop drivers are permissive -- they are NOT a substitute gate."
        )
    src_path = os.path.join(workdir, f"_gate_{stage}.{stage}")
    with open(src_path, "w", encoding="utf-8") as fh:
        fh.write(source)
    try:
        proc = subprocess.run(
            [exe, "-S", stage, src_path],
            capture_output=True, text=True, timeout=60,
        )
        return proc.returncode == 0, (proc.stdout + proc.stderr).strip()
    finally:
        try:
            os.unlink(src_path)
        except OSError:
            pass


def gate_both_dialects(workdir: str) -> list[tuple[str, str, bool, str]]:
    """Compile the fragment body under BOTH dialects + the vertex stage (AC6).

    Returns ``[(stage, version, ok, output), ...]``.
    """
    frag = read_frag_body()
    out = []
    for version in (VERSION_ES, VERSION_DESKTOP):
        ok, msg = validate_glsl(build_source(frag, version), "frag", workdir)
        out.append(("frag", version, ok, msg))
        ok, msg = validate_glsl(build_source(_VERT_BODY, version), "vert", workdir)
        out.append(("vert", version, ok, msg))
    return out


class MegaShader:
    """The stateful GL bit: standalone context + program + 150x1 RGBA8 FBO.

    Use as a context manager. One :meth:`evaluate` call == one draw == one
    keyframe -> ``n_rules`` bools.
    """

    def __init__(self, rules_texture: np.ndarray, frame_size: tuple[int, int]):
        import moderngl  # lazy: importing this module must not require a GL stack

        self._mgl = moderngl
        # Pre-declare every releasable handle so release() is safe to call at
        # ANY point during construction. _build() can raise after allocating a
        # standalone context and ~6 MB of textures -- and _selftest(), which
        # runs last, is *designed* to raise. Without this, a failed __init__
        # means `with MegaShader(...)` never enters, __exit__ never runs, and
        # the context leaks: precisely the class of failure the self-test exists
        # to catch, leaking on the path it catches it.
        self.ctx = None
        self.prog = None
        self.rules_tex = None
        self.frame_tex = None
        self.target = None
        self.fbo = None
        self.vao = None
        self.info = {}
        self._frame_size = frame_size
        try:
            self._build(moderngl, rules_texture, frame_size)
        except BaseException:
            self.release()
            raise

    def _build(self, moderngl, rules_texture: np.ndarray, frame_size) -> None:
        # create_standalone_context() is deprecated; require=330 gives the
        # desktop dialect. NB `require=300` would mean desktop GL 3.0, NOT ES.
        #
        # moderngl.Error is its own hierarchy, so it would sail past main()'s
        # diagnosed-exception tuple as a raw traceback. Re-raise as RuntimeError:
        # "no GPU / no driver / headless box with no EGL" is a normal operating
        # condition for this tool and deserves a diagnosed message, not a stack.
        try:
            self.ctx = moderngl.create_context(standalone=True, require=330)
        except Exception as exc:
            raise RuntimeError(
                f"could not create a standalone OpenGL 3.3 context ({exc}). "
                f"The bench needs a working GL driver; on a headless box this "
                f"usually means no EGL/OSMesa backend is available."
            ) from exc
        self.info = {
            "GL_VERSION": self.ctx.info["GL_VERSION"],
            "GL_RENDERER": self.ctx.info["GL_RENDERER"],
            "GL_VENDOR": self.ctx.info["GL_VENDOR"],
        }

        body = read_frag_body()
        self.prog = self.ctx.program(
            vertex_shader=build_source(_VERT_BODY, VERSION_DESKTOP),
            fragment_shader=build_source(body, VERSION_DESKTOP),
        )

        # Rules LUT: 150x3 RGBA32F. Texturing a float format is fine in ES 3.0
        # core; NEAREST because float textures are not filterable without
        # OES_texture_float_linear (and texelFetch never filters anyway).
        arr = np.ascontiguousarray(rules_texture.transpose(1, 0, 2), dtype="f4")
        self.rules_tex = self.ctx.texture((MAX_RULES, arr.shape[0]), 4, arr.tobytes(), dtype="f4")
        self.rules_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        w, h = frame_size
        # dtype "f1" == GL_RGB8, a NORMALIZED 8-bit texture sampled through a
        # plain sampler2D as floats in [0,1]. NOT "u1" -- in moderngl that spells
        # GL_RGB8UI, an INTEGER texture, which a sampler2D cannot legally read
        # (it needs usampler2D) and which fails silently rather than loudly.
        self.frame_tex = self.ctx.texture((w, h), 3, dtype="f1")
        self.frame_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        # 150x3 = 600 B is *accidentally* 4-aligned; 1920*3 likewise. That luck
        # dies the moment a dimension or format changes -- pin alignment to 1.
        self.frame_tex.alignment = 1

        # RGBA8, NOT RGBA32F: RGBA32F is not color-renderable in ES 3.0 core
        # (needs EXT_color_buffer_float) and glReadPixels only guarantees
        # GL_RGBA/GL_UNSIGNED_BYTE. Decoded with a `> 127` threshold CPU-side.
        # Again "f1" (GL_RGBA8), not "u1" (GL_RGBA8UI): the shader writes a vec4,
        # so an integer attachment would be an invalid pairing.
        self.target = self.ctx.texture((MAX_RULES, 1), 4, dtype="f1")
        self.target.alignment = 1
        self.fbo = self.ctx.framebuffer(color_attachments=[self.target])

        self.vao = self.ctx.vertex_array(self.prog, [])
        self.prog["uFrame"].value = 0
        self.prog["uRules"].value = 1
        self._selftest()

    def _selftest(self) -> None:
        """Prove the draw+readback pipeline works BEFORE any real frame runs.

        Earned the hard way: an integer-vs-normalized texture format mismatch
        (moderngl's "u1" is GL_RGBA8UI, not GL_RGBA8) made every readback return
        uninitialized memory. It did not raise -- it produced plausible-looking
        garbage that read as "the GPU port is broken" and cost a full accuracy
        run to notice. GL failures of this class are silent by nature, so assert
        the plumbing once, loudly, at construction.
        """
        self.fbo.use()
        self.ctx.viewport = (0, 0, MAX_RULES, 1)
        self.fbo.clear(0.0, 0.0, 0.0, 1.0)
        cleared = np.frombuffer(
            self.fbo.read(components=4, dtype="f1"), dtype=np.uint8
        ).reshape(MAX_RULES, 4)
        err = self.ctx.error
        if err != "GL_NO_ERROR":
            raise RuntimeError(
                f"GL error {err} during framebuffer readback self-test — the "
                f"render target and glReadPixels format disagree. Readback would "
                f"be garbage."
            )
        if cleared[:, 0].max() != 0 or cleared[:, 3].min() != 255:
            raise RuntimeError(
                "framebuffer readback self-test failed: a cleared RGBA8 target "
                f"read back as {cleared[0].tolist()}, expected [0, 0, 0, 255]."
            )

    def upload(self, frame_bgr: np.ndarray) -> None:
        """Upload one keyframe. ``frame_bgr`` is OpenCV-native BGR uint8.

        The shape check is not defensive noise: the texture was allocated at a
        fixed ``(w, h)`` and ``write()`` takes raw bytes, so a frame with the
        same byte count but transposed geometry (1440x1080 vs 1080x1440) would
        upload without complaint and produce garbage detections. Same reasoning
        that produced :meth:`_selftest` — assert the plumbing rather than trust
        caller discipline, because the failure is silent.
        """
        w, h = self._frame_size
        if frame_bgr.shape[:2] != (h, w) or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            raise ValueError(
                f"frame is {frame_bgr.shape}, but the frame texture was built "
                f"for (h={h}, w={w}, 3). Rebuild MegaShader for the new size — "
                f"a same-byte-count mismatch uploads silently and yields "
                f"transposed pixels, not an error."
            )
        self.frame_tex.write(np.ascontiguousarray(frame_bgr, dtype=np.uint8).tobytes())

    def draw_and_read(self) -> np.ndarray:
        """One draw + readback -> ``(150, 4)`` uint8."""
        self.fbo.use()
        self.ctx.viewport = (0, 0, MAX_RULES, 1)
        self.frame_tex.use(0)
        self.rules_tex.use(1)
        self.vao.render(self._mgl.TRIANGLES, vertices=3)
        raw = self.fbo.read(components=4, dtype="f1")
        return np.frombuffer(raw, dtype=np.uint8).reshape(MAX_RULES, 4)

    def __enter__(self) -> "MegaShader":
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def release(self) -> None:
        """Idempotent, and safe on a partially-constructed instance."""
        for obj in ("vao", "fbo", "target", "frame_tex", "rules_tex", "prog", "ctx"):
            handle = getattr(self, obj, None)
            if handle is None:
                continue
            try:
                handle.release()
            except Exception:
                pass
            setattr(self, obj, None)
