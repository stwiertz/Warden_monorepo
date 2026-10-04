#!/usr/bin/env node
// Story 12.4d — archive ONE end-to-end PERF-002 run from the reference device.
//
//   node apps/mobile/bench/12-4d/capture_run.mjs <runN>
//
// Clears logcat, snapshots thermal state, then waits for the pipeline's
// `[PERF-002] ... record={...}` line (logged at the end of a successful run,
// __DEV__ builds only). While it waits it samples the thermal status every 10 s,
// so the run's WORST status is recorded, not just its endpoints. Writes
// `run<N>.json` beside this script. Nothing here touches the app: the run is
// started by hand from the app UI (AC0a: the clock is runPipeline() entry ->
// `ready`, so the import copy that precedes it is outside the number anyway).
import { execFileSync, spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const run = process.argv[2];
if (!run) throw new Error("usage: capture_run.mjs <runN>");
const here = dirname(fileURLToPath(import.meta.url));
const TIMEOUT_MS = 20 * 60 * 1000;

const adb = (...args) => execFileSync("adb", args, { encoding: "utf8" });

function thermal() {
  const ts = adb("shell", "dumpsys", "thermalservice");
  const status = Number(/Thermal Status: (\d+)/.exec(ts)?.[1] ?? NaN);
  // "Current temperatures from HAL:" block — keep CPU/GPU/skin/battery rows.
  const block = ts.split("Current temperatures from HAL:")[1]?.split("Current cooling devices")[0] ?? "";
  const temps = {};
  for (const m of block.matchAll(/mValue=([\d.]+), mType=(\d+), mName=([^,]+), mStatus=(\d+)/g)) {
    temps[m[3]] = { celsius: Number(m[1]), type: Number(m[2]), status: Number(m[4]) };
  }
  // The HAL temperature block is EMPTY on this device; cooling devices with a
  // non-zero mValue are the throttling signal that is actually exposed.
  const cooling = {};
  for (const m of ts.matchAll(/CoolingDevice\{mValue=(\d+), mType=\d+, mName=([^}]+)\}/g)) {
    if (Number(m[1]) > 0) cooling[m[2]] = Number(m[1]);
  }
  const battery = adb("shell", "dumpsys", "battery");
  const batteryTenthsC = Number(/temperature: (\d+)/.exec(battery)?.[1] ?? NaN);
  return { at: new Date().toISOString(), status, battery_celsius: batteryTenthsC / 10, temps, active_cooling: cooling };
}

adb("logcat", "-c");
const before = thermal();
const samples = [];
const sampler = setInterval(() => {
  try {
    const t = thermal();
    samples.push({ at: t.at, status: t.status, battery_celsius: t.battery_celsius, active_cooling: t.active_cooling });
  } catch {}
}, 10_000);

console.log(`[run ${run}] thermal status ${before.status}, battery ${before.battery_celsius} °C — start the import in the app now.`);

const marks = [];
const lc = spawn("adb", ["logcat", "-v", "time", "-s", "ReactNativeJS:V", "WardenAnalyzer:V", "*:S"]);
let buf = "";
const timer = setTimeout(() => finish(new Error("timed out waiting for the [PERF-002] record line")), TIMEOUT_MS);

lc.stdout.on("data", (chunk) => {
  buf += chunk.toString();
  const lines = buf.split(/\r?\n/);
  buf = lines.pop();
  for (const line of lines) {
    if (line.includes("[PERF-002]") || line.includes("[PERF-009]") || line.includes("WardenAnalyzer")) {
      marks.push(line);
      console.log(line);
    }
    const m = /\[PERF-002\] sessionId=(\S+) record=(\{.*\})/.exec(line);
    if (m) finish(null, m[1], JSON.parse(m[2]));
    if (/\[PERF-002\] sessionId=\S+ ERROR/.test(line)) finish(new Error(line));
  }
});

function finish(err, sessionId, record) {
  clearTimeout(timer);
  clearInterval(sampler);
  lc.kill();
  const after = thermal();
  const out = {
    story: "12.4d",
    run: Number(run),
    fixture: "videos/V2/2026-04-27 22-05-34.mp4 (pushed as /sdcard/Download/warden-12-4d-capture.mp4)",
    device: adb("shell", "getprop", "ro.product.model").trim(),
    boundary: "runPipeline() entry -> updateSessionStatus('ready'); see story 12.4d AC0a",
    error: err ? String(err.message ?? err) : null,
    sessionId: sessionId ?? null,
    perf002: record ?? null,
    thermal: {
      before,
      after,
      samples,
      worst_status: Math.max(before.status, after.status, ...samples.map((s) => s.status)),
    },
    logcat: marks,
  };
  const file = join(here, `run${run}.json`);
  writeFileSync(file, JSON.stringify(out, null, 2) + "\n");
  console.log(`[run ${run}] ${err ? "FAILED" : "ok"} -> ${file}`);
  process.exit(err ? 1 : 0);
}
