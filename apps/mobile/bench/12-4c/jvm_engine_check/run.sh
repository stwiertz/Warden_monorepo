#!/usr/bin/env bash
# Story 12.4c — run the SHIPPED Kotlin evaluator against the PC oracle, on a
# desktop JVM, with no device.
#
# See JvmEngineCheck.kt for what this proves (the packer, the colour converter
# and the rule evaluator on real video planes) and what it does NOT (MediaCodec
# itself — that is the epic-end device run).
#
# Prerequisites, all of which the repo already has after an Android build:
#   * a JDK — Android Studio's JBR is on PATH in this environment
#   * the Kotlin compiler + stdlib + org.json jars in the Gradle cache
#   * `video_oracle.py oracle` already run (for video_oracle_fires.json)
#   * ffmpeg on PATH
#
#   bash run.sh "../../../../../videos/V2/2026-04-27 22-05-34.mp4" [FRAME_LIMIT]

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
VIDEO="${1:?usage: run.sh <video.mp4> [frame-limit]}"
LIMIT="${2:-0}"

CACHE="$HOME/.gradle/caches/modules-2/files-2.1"
KOTLIN_VER=2.1.20
# Git Bash on Windows: `java` is a Windows binary, so every path it is handed
# must be a Windows path. `cygpath -w` is a no-op-equivalent elsewhere (the
# fallback branch), which keeps this script readable on one OS without breaking
# on the other.
win() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
find_jar() { win "$(find "$CACHE/$1" -name "$2" | head -1)"; }

COMPILER="$(find_jar org.jetbrains.kotlin/kotlin-compiler-embeddable "kotlin-compiler-embeddable-$KOTLIN_VER.jar")"
STDLIB="$(find_jar org.jetbrains.kotlin/kotlin-stdlib "kotlin-stdlib-$KOTLIN_VER.jar")"
SCRIPT_RT="$(find_jar org.jetbrains.kotlin/kotlin-script-runtime "kotlin-script-runtime-$KOTLIN_VER.jar")"
DAEMON="$(find_jar org.jetbrains.kotlin/kotlin-daemon-embeddable "kotlin-daemon-embeddable-$KOTLIN_VER.jar")"
TROVE="$(find_jar org.jetbrains.intellij.deps/trove4j 'trove4j-*.jar')"
JSON="$(find_jar org.json/json 'json-*.jar')"
# kotlin-compiler-embeddable does not bundle coroutines; its phased CLI pipeline
# needs them on the classpath or it dies with `ClassNotFoundException:
# kotlinx.coroutines.CoroutineScope`. This is the COMPILER's dependency, not the
# compiled code's, so any recent build already in the Gradle cache will do.
COROUTINES="$(win "$(find "$CACHE/org.jetbrains.kotlinx/kotlinx-coroutines-core-jvm" -name 'kotlinx-coroutines-core-jvm-1.*.jar' | sort | tail -1)")"
# The IR backend emits nullability annotations and needs org.jetbrains:annotations
# on ITS OWN classpath to do so (NoClassDefFoundError: org/jetbrains/annotations/
# NotNull). Also the compiler's dependency, not the compiled code's.
ANNOTATIONS="$(win "$(find "$CACHE/org.jetbrains/annotations" -name 'annotations-2*.jar' | sort | tail -1)")"

for jar in "$COMPILER" "$STDLIB" "$JSON"; do
  [ -n "$jar" ] || { echo "missing a required jar in the Gradle cache" >&2; exit 1; }
done

OUT="$HERE/build"
mkdir -p "$OUT"

# 🔴 The sources under test are the TRACKED ones in plugins/kotlin/, not a copy:
# a harness that compiled its own copy would prove something about the copy.
KOTLIN_SRC="$REPO/apps/mobile/plugins/kotlin"

echo "== compiling the shipped Kotlin (no Android on the classpath) =="
java -cp "$COMPILER;$STDLIB;$SCRIPT_RT;$DAEMON;$TROVE;$COROUTINES;$ANNOTATIONS" \
  org.jetbrains.kotlin.cli.jvm.K2JVMCompiler \
  -no-stdlib -nowarn \
  -cp "$STDLIB;$JSON" \
  -d "$OUT/classes" \
  "$KOTLIN_SRC/WardenRulePacker.kt" \
  "$KOTLIN_SRC/WardenColorConvert.kt" \
  "$KOTLIN_SRC/WardenCpuBaseline.kt" \
  "$HERE/JvmStubs.kt" \
  "$HERE/JvmEngineCheck.kt"

# ⚠️ 3.1 GB for the full capture — 1061 keyframes x 3.1 MB of raw I420. It is
# written to `build/` (gitignored) and kept only so a re-run is cheap; delete it
# when you are done. Decoding once and comparing against a stored file, rather
# than piping, keeps the comparison reproducible frame-for-frame.
RAW="$OUT/keyframes_i420.raw"
if [ ! -f "$RAW" ]; then
  echo "== decoding keyframes to raw I420 (same FFmpeg pass the oracle used) =="
  ffmpeg -nostdin -hide_banner -loglevel error \
    -skip_frame nokey -i "$VIDEO" -an -sn -dn \
    -fps_mode passthrough -f rawvideo -pix_fmt yuv420p "$RAW"
fi

echo "== running the evaluator against the oracle =="
cd "$HERE"
java -cp "$(win "$OUT/classes");$STDLIB;$JSON" team.warden.mobile.JvmEngineCheckKt \
  "$(win "$REPO/apps/tooling/output/map_configs/map_config.v2.json")" \
  "$(win "$RAW")" \
  "$(win "$HERE/../video_oracle_fires.json")" \
  "$LIMIT"
