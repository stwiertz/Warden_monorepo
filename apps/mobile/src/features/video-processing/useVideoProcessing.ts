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

// Story 12.4c removed the "keyframes" label with the stage: extraction and
// detection are one native call now, so "Extracting keyframes" would have named
// a step the user can no longer be in.
const STAGE_LABELS: Record<ProcessingStage, string> = {
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
      // Story 1.13: no config gate. The pipeline always has a map config — the
      // bundled one, or a post-auth overlay cached earlier — so processing
      // never waits on, or is refused by, a Firestore read.
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
