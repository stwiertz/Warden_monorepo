import { useState, useEffect, useCallback, useRef } from "react";
import { runProcessingPipeline, getCheckpoint } from "./processingPipeline";
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

    // Check for existing checkpoint (crash recovery)
    const checkpoint = getCheckpoint(sessionId);
    if (checkpoint) {
      setStage(checkpoint);
    }

    runProcessingPipeline(sessionId, (currentStage, overallProgress) => {
      setStage(currentStage);
      setProgress(overallProgress);
    })
      .then(() => {
        setStatus("completed");
        setProgress(100);
        isRunning.current = false;
      })
      .catch((err) => {
        setStatus("error");
        setError(
          err instanceof Error ? err.message : "Processing failed"
        );
        isRunning.current = false;
      });
  }, [sessionId]);

  return { progress, stage, status, error, startProcessing };
}
