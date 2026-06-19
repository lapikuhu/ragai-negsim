import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RagProfilesPage } from "./RagProfilesPage";

const llmCatalogState = vi.hoisted(() => ({
  isLoading: false,
  isError: false,
  data: {
    providers: [
      { provider: "openai", models: [{ name: "gpt-4o-mini" }] },
      { provider: "ollama", models: [{ name: "qwen2.5:3b", size_gib: 2.2 }] },
    ],
    gpu_memory_gib: 8,
  },
  error: null as Error | null,
  refetch: vi.fn(),
}));

vi.mock("@/features/ragProfiles/ragProfileQueries", () => ({
  useRagProfilesQuery: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        id: 500,
        name: "Default CRAG",
        strategy: "crag",
        config: { top_k: 4, reranker: "cross_encoder", top_n: 3, max_rewrite_attempts: 2 },
        created_by_user_id: 1,
        last_edit_by_user_id: null,
        created_at: "2026-06-14T12:00:00Z",
        last_updated: "2026-06-14T12:00:00Z",
        simulation_ids: [31],
      },
    ],
    refetch: vi.fn(),
  }),
  useRagProfileDefinitionsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        strategy: "crag",
        label: "Corrective RAG",
        fields: [
          {
            name: "reranker",
            kind: "enum",
            label: "Reranker",
            required: true,
            default: "cross_encoder",
            options: ["cross_encoder", "none"],
          },
        ],
      },
      {
        strategy: "graphrag",
        label: "Knowledge Graph RAG",
        fields: [
          {
            name: "retrieval_mode",
            kind: "enum",
            label: "Retrieval mode",
            required: true,
            default: "semantic",
            options: ["semantic", "cypher", "hybrid"],
          },
        ],
      },
    ],
    refetch: vi.fn(),
  }),
  useCreateRagProfileMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useUpdateRagProfileMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useCopyRagProfileMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useDeleteRagProfileMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

vi.mock("@/features/knowledgeGraphs/knowledgeGraphQueries", () => ({
  useKnowledgeGraphsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/llmModels/llmModelQueries", () => ({
  useLlmModelCatalogQuery: () => ({
    isLoading: llmCatalogState.isLoading,
    isError: llmCatalogState.isError,
    data: llmCatalogState.data,
    error: llmCatalogState.error,
    refetch: llmCatalogState.refetch,
  }),
}));

describe("RagProfilesPage", () => {
  it("renders page content while the LLM catalog is still loading", () => {
    llmCatalogState.isLoading = true;
    llmCatalogState.isError = false;
    llmCatalogState.data = undefined as never;
    llmCatalogState.error = null;

    render(<RagProfilesPage />);

    expect(screen.getByText("Create RAG profile")).toBeInTheDocument();
    expect(screen.getByText("Loading models...")).toBeInTheDocument();
    expect(screen.queryByText("Loading RAG profiles...")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create profile" })).toBeDisabled();
  });

  it("shows an inline warning when the LLM catalog fails without blocking the page", () => {
    llmCatalogState.isLoading = false;
    llmCatalogState.isError = true;
    llmCatalogState.data = undefined as never;
    llmCatalogState.error = new Error("Catalog unavailable");

    render(<RagProfilesPage />);

    expect(screen.getByText("Create RAG profile")).toBeInTheDocument();
    expect(screen.getByText("Catalog unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Unable to load RAG profiles")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create profile" })).toBeDisabled();
  });

  it("renders both available strategies in the create selector", () => {
    llmCatalogState.isLoading = false;
    llmCatalogState.isError = false;
    llmCatalogState.data = {
      providers: [
        { provider: "openai", models: [{ name: "gpt-4o-mini" }] },
        { provider: "ollama", models: [{ name: "qwen2.5:3b", size_gib: 2.2 }] },
      ],
      gpu_memory_gib: 8,
    };
    llmCatalogState.error = null;

    render(<RagProfilesPage />);

    expect(screen.getByRole("option", { name: "Corrective RAG" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Knowledge Graph RAG" })).toBeInTheDocument();
  });

  it("shows used profiles as locked for deletion", () => {
    llmCatalogState.isLoading = false;
    llmCatalogState.isError = false;
    llmCatalogState.data = {
      providers: [
        { provider: "openai", models: [{ name: "gpt-4o-mini" }] },
        { provider: "ollama", models: [{ name: "qwen2.5:3b", size_gib: 2.2 }] },
      ],
      gpu_memory_gib: 8,
    };
    llmCatalogState.error = null;

    render(<RagProfilesPage />);

    expect(screen.getByText("In use")).toBeInTheDocument();
    expect(screen.getByText("Locked after simulation use.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });
});
