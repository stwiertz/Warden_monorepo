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

export function useVideoImport(): UseVideoImportReturn {
  const navigation = useNavigation<NavigationProp>();
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<ValidationError | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const importVideo = useCallback(async () => {
    setImporting(true);
    setError(null);

    try {
      const outcome = await pickAndImportVideo();

      if (!outcome.success) {
        if (outcome.error.code !== "PICKER_CANCELLED") {
          setError(outcome.error);
        }
        return;
      }

      navigation.navigate("Processing", {
        sessionId: outcome.result.sessionId,
      });
    } catch (e) {
      setError({
        code: "FILE_NOT_FOUND",
        message: "An unexpected error occurred during import.",
      });
    } finally {
      setImporting(false);
    }
  }, [navigation]);

  return { importing, error, clearError, importVideo };
}
