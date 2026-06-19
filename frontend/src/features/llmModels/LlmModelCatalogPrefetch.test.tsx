import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LlmModelCatalogPrefetch } from "./LlmModelCatalogPrefetch";

const authState = vi.hoisted(() => ({
  isAuthenticated: false,
  isLoading: false,
}));

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => authState,
}));

describe("LlmModelCatalogPrefetch", () => {
  it("prefetches the catalog after auth is ready", async () => {
    authState.isAuthenticated = true;
    authState.isLoading = false;
    const client = new QueryClient();
    const prefetchQuery = vi.spyOn(client, "prefetchQuery").mockResolvedValue(undefined);

    render(
      <QueryClientProvider client={client}>
        <LlmModelCatalogPrefetch />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(prefetchQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          queryKey: ["llm-models", "catalog"],
          staleTime: 60 * 60 * 1000,
          gcTime: 120 * 60 * 1000,
        }),
      );
    });
  });

  it("does not prefetch while auth is loading or unauthenticated", () => {
    authState.isAuthenticated = false;
    authState.isLoading = true;
    const client = new QueryClient();
    const prefetchQuery = vi.spyOn(client, "prefetchQuery").mockResolvedValue(undefined);

    render(
      <QueryClientProvider client={client}>
        <LlmModelCatalogPrefetch />
      </QueryClientProvider>,
    );

    expect(prefetchQuery).not.toHaveBeenCalled();
  });
});
