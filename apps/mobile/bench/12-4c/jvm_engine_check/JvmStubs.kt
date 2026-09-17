package team.warden.mobile

import java.nio.ByteBuffer

// Story 12.4c — the ONE declaration this off-device harness has to supply.
//
// `WardenYuvFrame.of(kf)` takes a `WardenKeyframe`, which lives in
// `WardenKeyframeDecoder.kt` — a file that imports `android.media.*` and
// therefore cannot compile on a desktop JVM. Rather than pull Android in (or,
// worse, edit the shipped converter to suit a harness), the harness declares the
// plain data carrier the converter needs.
//
// 🔴 THIS IS A CARRIER, NOT A REIMPLEMENTATION. It must stay field-for-field
// identical to the real one; if `WardenKeyframe` ever gains a field the
// converter reads, this stub stops compiling, which is the intended failure. The
// code UNDER TEST — the packer, the converter and the evaluator — is compiled
// from `plugins/kotlin/` verbatim.
//
// The harness itself builds `WardenYuvFrame` directly from FFmpeg's planes, so
// `of()` is never called; this exists purely to satisfy the compiler.
class WardenKeyframe(
    val presentationTimeUs: Long,
    val width: Int,
    val height: Int,
    val planes: Array<ByteBuffer>,
    val rowStrides: IntArray,
    val pixelStrides: IntArray,
)
