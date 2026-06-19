import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RagProfilesPage } from "./RagProfilesPage";

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
    isLoading: false,
    isError: false,
    data: {
      providers: [
        { provider: "openai", models: [{ name: "gpt-4o-mini" }] },
        { provider: "ollama", models: [{ name: "qwen2.5:3b", size_gib: 2.2 }] },
      ],
      gpu_memory_gib: 8,
    },
    refetch: vi.fn(),
  }),
}));

describe("RagProfilesPage", () => {
  it("renders both available strategies in the create selector", () => {
    render(<RagProfilesPage />);

    expect(screen.getByRole("option", { name: "Corrective RAG" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Knowledge Graph RAG" })).toBeInTheDocument();
  });

  it("shows used profiles as locked for deletion", () => {
    render(<RagProfilesPage />);

    expect(screen.getByText("In use")).toBeInTheDocument();
    expect(screen.getByText("Locked after simulation use.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });
});
