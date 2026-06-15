import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KnowledgeGraphsPage } from "./KnowledgeGraphsPage";

const { useKnowledgeGraphsQuery, mutateAsync } = vi.hoisted(() => ({
  useKnowledgeGraphsQuery: vi.fn(),
  mutateAsync: vi.fn(),
}));

vi.mock("@/features/knowledgeGraphs/knowledgeGraphQueries", () => ({
  useKnowledgeGraphsQuery,
  useCreateKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync }),
  useBuildKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useDeleteKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useCorpusIndicesQuery: () => ({
    data: [{ id: 77, name: "Main index", status: "built" }],
  }),
}));

describe("KnowledgeGraphsPage", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
    useKnowledgeGraphsQuery.mockReturnValue({
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
    });
  });

  it("defaults to schema with chunk structure enabled", () => {
    render(<KnowledgeGraphsPage />);

    expect(screen.getByRole("radio", { name: /Schema/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: /Simple/ })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Include chunk structure/ })).toBeChecked();
  });

  it("shows short explanations for each extractor option", () => {
    render(<KnowledgeGraphsPage />);

    expect(screen.getByText(/typed negotiation concepts and relationships/i)).toBeInTheDocument();
    expect(screen.getByText(/unrestricted subject-relation-object triples/i)).toBeInTheDocument();
    expect(screen.getByText(/document relationships such as previous and next chunks/i)).toBeInTheDocument();
  });

  it("submits schema plus implicit by default", async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({});
    render(<KnowledgeGraphsPage />);

    await user.type(screen.getByLabelText("Name"), "Graph with structure");
    await user.selectOptions(screen.getByLabelText("Built corpus index"), "77");
    await user.click(screen.getByRole("button", { name: "Create graph" }));

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Graph with structure",
        corpus_index_id: 77,
        build_config: expect.objectContaining({
          extractors: ["schema", "implicit"],
        }),
      }),
    );
  });

  it("submits simple without implicit when structure is disabled", async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({});
    render(<KnowledgeGraphsPage />);

    await user.click(screen.getByRole("radio", { name: /Simple/ }));
    await user.click(screen.getByRole("checkbox", { name: /Include chunk structure/ }));
    await user.type(screen.getByLabelText("Name"), "Simple graph");
    await user.selectOptions(screen.getByLabelText("Built corpus index"), "77");
    await user.click(screen.getByRole("button", { name: "Create graph" }));

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Simple graph",
        corpus_index_id: 77,
        build_config: expect.objectContaining({
          extractors: ["simple"],
        }),
      }),
    );
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
