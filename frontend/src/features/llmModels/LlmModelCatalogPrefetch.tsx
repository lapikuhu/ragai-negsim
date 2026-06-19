import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/app/AuthProvider";
import { llmModelCatalogQueryOptions } from "@/features/llmModels/llmModelQueries";

export function LlmModelCatalogPrefetch() {
  const auth = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!auth.isAuthenticated || auth.isLoading) {
      return;
    }
    void queryClient.prefetchQuery(llmModelCatalogQueryOptions());
  }, [auth.isAuthenticated, auth.isLoading, queryClient]);

  return null;
}
