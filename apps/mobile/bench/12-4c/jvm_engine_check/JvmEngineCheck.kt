package team.warden.mobile

import java.io.DataInputStream
import java.io.File
import java.nio.ByteBuffer

// Story 12.4c — run the SHIPPED Kotlin evaluator on the PC, against the PC
// oracle, with no device in the loop.
//
// WHY THIS EXISTS
// ---------------
// AC10 asks for an independent video oracle and makes it "this story's end-to-end
// parity gate for the wired pipeline", while noting that the DEVICE half belongs
// to the epic-end device pass. That leaves a gap this harness fills: the oracle's
// fires are numpy + cv2, and comparing them to the device is the only check that
// ever runs our Kotlin — so a defect in `WardenColorConvert` or
// `WardenCpuBaseline` would sit undetected until a phone is plugged in.
//
// `WardenColorConvert`, `WardenCpuBaseline` and `WardenRulePacker` import NOTHING
// from Android except `org.json`, so they run on a desktop JVM unchanged. This
// harness feeds them the same raw I420 planes FFmpeg produced for the oracle and
// compares fire bits, rule by rule, frame by frame.
//
// WHAT IT PROVES AND WHAT IT DOES NOT
//   * PROVES: the packer, the BT.709 limited-range + nearest-chroma converter and
//     the integer rule evaluator agree with the Python reference on real video
//     planes — including the 9 wrap-branch rules and the 68 full-circle ones.
//   * DOES NOT PROVE: MediaCodec. The planes here come from FFmpeg, not from the
//     device decoder, and plane STRIDES on a real codec are the decoder's
//     (rowStride >= width, pixelStride 2 for NV12). That half is the epic-end
//     device run: `video_oracle.py compare` against a real `analyzeSession` dump.
//     To keep the gap honest rather than invisible, the I420 planes are fed
//     through the SAME `WardenYuvFrame` stride arithmetic the decoder path uses.
//
// Build + run: bench/12-4c/jvm_engine_check/run.sh

private const val REF_W = 1920
private const val REF_H = 1080

fun main(args: Array<String>) {
    val configPath = args[0]
    val rawPath = args[1]      // raw yuv420p planes, one frame after another
    val oraclePath = args[2]   // video_oracle_fires.json
    val limit = if (args.size > 3) args[3].toInt() else 0

    val configJson = File(configPath).readText()
    val packed = WardenRulePacker.packRules(configJson, REF_W, REF_H)
    println("packed ${packed.nRules} rules")

    // The oracle's fire rows, in frame order. Parsed with a deliberately dumb
    // scanner rather than a JSON library: this file must not acquire a
    // dependency the app does not have, and the field it needs is unambiguous.
    val oracleFires = Regex("\"fires\": \"([0-9a-f]+)\"")
        .findAll(File(oraclePath).readText())
        .map { it.groupValues[1] }
        .toList()
    println("oracle carries ${oracleFires.size} fire rows")

    val ySize = REF_W * REF_H
    val cSize = (REF_W / 2) * (REF_H / 2)
    val frameSize = ySize + 2 * cSize

    var frames = 0
    var disagreements = 0
    var framesWithDisagreement = 0
    val perRule = IntArray(packed.nRules)
    val examples = StringBuilder()

    DataInputStream(File(rawPath).inputStream().buffered(1 shl 20)).use { input ->
        val buf = ByteArray(frameSize)
        while (frames < oracleFires.size && (limit == 0 || frames < limit)) {
            try {
                input.readFully(buf)
            } catch (_: Exception) {
                break
            }
            // I420 from FFmpeg: three planar planes, pixelStride 1, rowStride =
            // plane width. Read through WardenYuvFrame so the stride arithmetic
            // under test is the shipped one.
            val y = ByteBuffer.wrap(buf, 0, ySize).slice()
            val u = ByteBuffer.wrap(buf, ySize, cSize).slice()
            val v = ByteBuffer.wrap(buf, ySize + cSize, cSize).slice()
            val frame = WardenYuvFrame(
                y, REF_W, 1,
                u, REF_W / 2, 1,
                v, REF_W / 2, 1,
                REF_W, REF_H,
            )
            val bits = WardenCpuBaseline.evaluateYuv(frame, packed)
            val expected = hexToBits(oracleFires[frames], packed.nRules)
            var bad = 0
            for (i in 0 until packed.nRules) {
                if (bits[i] != expected[i]) {
                    bad++
                    perRule[i]++
                    if (examples.length < 1200) {
                        val ref = packed.refs[i]
                        examples.append(
                            "frame $frames rule $i (${ref.owningClass}/${ref.zoneId}): " +
                                "kotlin=${bits[i]} oracle=${expected[i]}\n"
                        )
                    }
                }
            }
            if (bad > 0) framesWithDisagreement++
            disagreements += bad
            frames++
            if (frames % 100 == 0) println("  $frames frames, $disagreements disagreements")
        }
    }

    val decisions = frames * packed.nRules
    println()
    println("frames compared        : $frames")
    println("rule-frame decisions   : $decisions")
    println("frames with any diff   : $framesWithDisagreement")
    println("total disagreements    : $disagreements")
    if (disagreements == 0) {
        println("[PASS] EXACT PARITY - the shipped Kotlin evaluator reproduces the PC oracle")
    } else {
        println("[FAIL]")
        println(examples)
        val worst = perRule.withIndex().filter { it.value > 0 }.sortedByDescending { it.value }
        for ((i, count) in worst.take(10)) {
            val ref = packed.refs[i]
            println("  rule $i ${ref.owningClass}/${ref.zoneId}: $count")
        }
    }
    File("jvm_engine_check_result.json").writeText(
        """{"frames": $frames, "rule_frame_decisions": $decisions, """ +
            """"frames_with_disagreement": $framesWithDisagreement, """ +
            """"total_disagreements": $disagreements, """ +
            """"exact_parity": ${disagreements == 0}}"""
    )
    if (disagreements != 0) kotlin.system.exitProcess(1)
}

/** 4 bits per hex char, LSB first — WardenEngineBench.bitsToHex's packing. */
private fun hexToBits(hex: String, n: Int): BooleanArray {
    val out = BooleanArray(n)
    for (i in 0 until n) {
        val nibble = Character.digit(hex[i / 4], 16)
        out[i] = (nibble shr (i % 4)) and 1 == 1
    }
    return out
}
