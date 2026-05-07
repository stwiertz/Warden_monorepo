import { useState, useEffect, useCallback, useRef } from "react";
import { runProcessingPipeline, getCheckpoint } from "./processingPipeline";
import {
  getBootstrapPromise,
  isVideoProcessingBlocked,
} from "./detectionConfigBootstrap";
import type { ProcessingStage } from "./types";

interface UseVideoProcessingReturn {
  progress: number;
  stage: ProcessingStage | null;
  status: "idle" | "processing" | "completed" | "error";
  error: string | null;
  startProcessing: () => void;
}

const STAGE_LABELS: Record<ProcessingStage, string> = {
  keyframes: "Extracting keyframes",
  detection: "Analyzing frames",
  segmentation: "Segmenting maps",
  results: "Extracting result frames",
};

export function getStageLabelFor(stage: ProcessingStage | null): string {
  if (!stage) return "Preparing...";
  return STAGE_LABELS[stage];
}

export function useVideoProcessing(
  sessionId: string
): UseVideoProcessingReturn {
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<ProcessingStage | null>(null);
  const [status, setStatus] = useState<
    "idle" | "processing" | "completed" | "error"
  >("idle");
  const [error, setError] = useState<string | null>(null);
  const isRunning = useRef(false);

  const startProcessing = useCallback(() => {
    if (isRunning.current) return;
    isRunning.current = true;
    setStatus("processing");
    setError(null);

    void (async () => {
      // Await bootstrap before reading the gate — otherwise a fast-tapping
      // user can reach this entry point in the offline-first-launch case
      // before the flag is written, bypassing AC 4.
      const pending = getBootstrapPromise();
      if (pending) {
        try {
          await pending;
        } catch {
          // bootstrap is contractually non-throwing; defensive only.
        }
      }

      const block = isVideoProcessingBlocked();
      if (block.blocked) {
        setStatus("error");
        setError(block.reason ?? "Video processing is unavailable.");
        isRunning.current = false;
        return;
      }

      const checkpoint = getCheckpoint(sessionId);
      if (checkpoint) {
        setStage(checkpoint);
      }

      try {
        await runProcessingPipeline(sessionId, {
          onProgress: (currentStage, overallProgress) => {
            setStage(currentStage);
            setProgress(overallProgress);
          },
        });
        setStatus("completed");
        setProgress(100);
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Processing failed");
      } finally {
        isRunning.current = false;
      }
    })();
  }, [sessionId]);

  return { progress, stage, status, error, startProcessing };
}
