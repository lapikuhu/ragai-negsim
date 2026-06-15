import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { KnowledgeGraphsPage } from "./KnowledgeGraphsPage";

vi.mock("@/features/knowledgeGraphs/knowledgeGraphQueries", () => ({
  useKnowledgeGraphsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        id: 1,
        name: "Negotiation ontology",
        corpus_index_id: 77,
        build_config: {
          llm_provider: "openai",
          llm_model: "gpt-4o-mini",
          embedding_provider: "openai",
          embedding_model: "text-embedding-3-small",
          extractors: ["schema"],
        },
        status: "failed",
        active_generation: "g1",
        latest_build_error:
          "Neo4j persistence produced an empty graph (nodes=0, relationships=0)",
        locked_at: "2026-06-14T12:00:00Z",
        built_at: "2026-06-14T11:00:00Z",
        created_at: "2026-06-14T10:00:00Z",
        last_updated: "2026-06-14T12:00:00Z",
        rag_profile_ids: [4],
        simulation_ids: [9],
        active_job_id: null,
      },
    ],
    refetch: vi.fn(),
  }),
  useCreateKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useBuildKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useDeleteKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useCorpusIndicesQuery: () => ({
    data: [{ id: 77, name: "Main index", status: "built" }],
  }),
}));

describe("KnowledgeGraphsPage", () => {
  it("exposes each supported knowledge graph extractor", () => {
    render(<KnowledgeGraphsPage />);

    expect(screen.getByRole("checkbox", { name: "Simple" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Implicit" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Schema" })).toBeInTheDocument();
  });

  it("shows a used graph as permanently locked", () => {
    render(<KnowledgeGraphsPage />);

    expect(screen.getByText("Negotiation ontology")).toBeInTheDocument();
    expect(screen.getByText("Permanently locked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rebuild" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
  });

  it("shows the latest build error in the graph list", () => {
    render(<KnowledgeGraphsPage />);

    expect(
      screen.getByText(
        "Neo4j persistence produced an empty graph (nodes=0, relationships=0)",
      ),
    ).toBeInTheDocument();
  });
});
