import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KnowledgeGraphsPage } from "./KnowledgeGraphsPage";

const { useKnowledgeGraphsQuery, mutateAsync } = vi.hoisted(() => ({
  useKnowledgeGraphsQuery: vi.fn(),
  mutateAsync: vi.fn(),
}));

const llmCatalogState = vi.hoisted(() => ({
  isLoading: false,
  isError: false,
  data: {
    providers: [
      { provider: "openai", models: [{ name: "gpt-4o-mini" }, { name: "gpt-4o" }] },
      { provider: "ollama", models: [{ name: "qwen2.5:3b", size_gib: 2.2 }] },
    ],
    gpu_memory_gib: 8,
  },
  error: null as Error | null,
  refetch: vi.fn(),
}));

vi.mock("@/features/knowledgeGraphs/knowledgeGraphQueries", () => ({
  useKnowledgeGraphsQuery,
  useCreateKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync }),
  useBuildKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useDeleteKnowledgeGraphMutation: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useCorpusIndicesQuery: () => ({
    isLoading: false,
    isError: false,
    data: [{ id: 77, name: "Main index", status: "built" }],
    refetch: vi.fn(),
  }),
  useEmbeddingModelsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        name: "text-embedding-3-small",
        provider: "openai",
        display_name: "OpenAI text-embedding-3-small",
        dimensionality: 1536,
        normalized: false,
      },
      {
        name: "mini-l6-v2",
        provider: "huggingface",
        display_name: "Sentence Transformers all-MiniLM-L6-v2",
        dimensionality: 384,
        normalized: true,
      },
    ],
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

describe("KnowledgeGraphsPage", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
    llmCatalogState.isLoading = false;
    llmCatalogState.isError = false;
    llmCatalogState.data = {
      providers: [
        { provider: "openai", models: [{ name: "gpt-4o-mini" }, { name: "gpt-4o" }] },
        { provider: "ollama", models: [{ name: "qwen2.5:3b", size_gib: 2.2 }] },
      ],
      gpu_memory_gib: 8,
    };
    llmCatalogState.error = null;
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

  it("renders page content while the LLM catalog is still loading", () => {
    llmCatalogState.isLoading = true;
    llmCatalogState.data = undefined as never;

    render(<KnowledgeGraphsPage />);

    expect(screen.getByText("Create graph definition")).toBeInTheDocument();
    expect(screen.getByText("Loading models...")).toBeInTheDocument();
    expect(screen.queryByText("Loading knowledge graphs...")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create graph" })).toBeDisabled();
  });

  it("shows an inline warning when the LLM catalog fails without blocking the page", () => {
    llmCatalogState.isError = true;
    llmCatalogState.data = undefined as never;
    llmCatalogState.error = new Error("Catalog unavailable");

    render(<KnowledgeGraphsPage />);

    expect(screen.getByText("Create graph definition")).toBeInTheDocument();
    expect(screen.getByText("Catalog unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Unable to load knowledge graphs.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create graph" })).toBeDisabled();
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

  it("populates extraction and embedding model dropdowns", () => {
    render(<KnowledgeGraphsPage />);

    expect(screen.getByRole("option", { name: "gpt-4o-mini" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "gpt-4o" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "OpenAI text-embedding-3-small" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Sentence Transformers all-MiniLM-L6-v2" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Embedding provider")).not.toBeInTheDocument();
  });

  it("switches extraction models when provider changes", async () => {
    const user = userEvent.setup();
    render(<KnowledgeGraphsPage />);

    await user.selectOptions(screen.getByLabelText("Extraction provider"), "ollama");

    expect(screen.getByRole("option", { name: "qwen2.5:3b (2.2 GiB)" })).toBeInTheDocument();
    expect(screen.getByLabelText("Extraction model")).toHaveValue("qwen2.5:3b");
  });

  it("submits schema plus implicit by default", async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValue({});
    render(<KnowledgeGraphsPage />);

    await user.type(screen.getByLabelText("Name"), "Graph with structure");
    await user.selectOptions(screen.getByLabelText("Built corpus index"), "77");
    await user.selectOptions(screen.getByLabelText(/Embedding model/), "mini-l6-v2");
    await user.click(screen.getByRole("button", { name: "Create graph" }));

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Graph with structure",
        corpus_index_id: 77,
        build_config: expect.objectContaining({
          llm_provider: "openai",
          llm_model: "gpt-4o-mini",
          embedding_model: "mini-l6-v2",
          extractors: ["schema", "implicit"],
        }),
      }),
    );
    expect(mutateAsync.mock.calls[0][0].build_config).not.toHaveProperty("embedding_provider");
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
