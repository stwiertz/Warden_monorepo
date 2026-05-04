import { useState, useCallback } from "react";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { pickAndImportVideo } from "./videoImportService";
import type { ValidationError } from "./types";
import type { RootStackParamList } from "../../app/RootNavigator";

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

interface UseVideoImportReturn {
  importing: boolean;
  error: ValidationError | null;
  clearError: () => void;
  importVideo: () => Promise<void>;
}

export interface ImportFlowDeps {
  onError: (error: ValidationError) => void;
  onSuccess: (sessionId: string) => void;
}

// Pure orchestration — extracted from the hook so the picker → validation →
// session → navigation flow can be unit-tested without React Navigation or
// react-test-renderer. PICKER_CANCELLED is intentionally swallowed.
export async function executeImportFlow(deps: ImportFlowDeps): Promise<void> {
  try {
    const outcome = await pickAndImportVideo();
    if (!outcome.success) {
      if (outcome.error.code !== "PICKER_CANCELLED") {
        deps.onError(outcome.error);
      }
      return;
    }
    deps.onSuccess(outcome.result.sessionId);
  } catch (e) {
    deps.onError({
      code: "UNKNOWN_ERROR",
      message:
        e instanceof Error
          ? e.message
          : "An unexpected error occurred during import.",
    });
  }
}

export function useVideoImport(): UseVideoImportReturn {
  const navigation = useNavigation<NavigationProp>();
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<ValidationError | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const importVideo = useCallback(async () => {
    setImporting(true);
    setError(null);
    await executeImportFlow({
      onError: setError,
      onSuccess: (sessionId) =>
        navigation.navigate("Processing", { sessionId }),
    });
    setImporting(false);
  }, [navigation]);

  return { importing, error, clearError, importVideo };
}
