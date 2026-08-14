import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import { SimulationsPage } from "./SimulationsPage";

const createSimulation = vi.fn();
const navigate = vi.fn();
const retrievalOptionsQueryState = vi.hoisted(() => ({
  isLoading: false,
  isError: false,
  error: null as unknown,
  refetch: vi.fn(),
  responses: {
    500: {
      mode: "dense",
      dense_indices: [{ id: 77, name: "Index A" }],
      bm25_indices: [],
      compatible_pairs: [],
    },
    502: {
      mode: "bm25",
      dense_indices: [],
      bm25_indices: [{ id: 88, name: "BM25 A" }],
      compatible_pairs: [],
    },
    503: {
      mode: "hybrid",
      dense_indices: [
        { id: 77, name: "Index A" },
        { id: 78, name: "Index B" },
      ],
      bm25_indices: [
        { id: 88, name: "BM25 A" },
        { id: 89, name: "BM25 B" },
      ],
      compatible_pairs: [
        { corpus_index_id: 77, bm25_index_id: 88 },
        { corpus_index_id: 78, bm25_index_id: 89 },
      ],
    },
  } as Record<number, {
    mode: "dense" | "bm25" | "hybrid";
    dense_indices: { id: number; name: string }[];
    bm25_indices: { id: number; name: string }[];
    compatible_pairs: { corpus_index_id: number; bm25_index_id: number }[];
  }>,
  calls: [] as Array<{ corpusId?: number; ragProfileId?: number; enabled: boolean }>,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    Link: ({ children }: { children: ReactNode }) => <>{children}</>,
    useNavigate: () => navigate,
  };
});

vi.mock("@/features/simulations/simulationQueries", () => ({
  useSimulationsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn(),
  }),
  useCreateSimulationMutation: () => ({
    isPending: false,
    mutateAsync: createSimulation,
  }),
  useSimulationRetrievalOptionsQuery: (
    corpusId?: number,
    ragProfileId?: number,
    enabled = true,
  ) => ({
    ...(retrievalOptionsQueryState.calls.push({ corpusId, ragProfileId, enabled }), {}),
    isLoading: retrievalOptionsQueryState.isLoading,
    isError: retrievalOptionsQueryState.isError,
    error: retrievalOptionsQueryState.error,
    refetch: retrievalOptionsQueryState.refetch,
    data: enabled && corpusId && ragProfileId
      ? retrievalOptionsQueryState.responses[ragProfileId]
      : undefined,
  }),
}));

vi.mock("@/features/corpora/corpusQueries", () => ({
  useCorporaQuery: () => ({
    isLoading: false,
    isError: false,
    data: [{ id: 11, name: "Corpus A" }],
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useCorpusIndicesQuery: () => ({
    isLoading: false,
    isError: false,
    data: [{ id: 77, corpus_id: 11, chunking_profile_id: 3, indexed_document_chunk_ids: [1, 2], status: "built", name: "Index A" }],
    refetch: vi.fn(),
  }),
  useChunkingProfilesQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn(),
  }),
  useVectorStoresQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn(),
  }),
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
        knowledge_graph_index_id: null,
        config: { bm25_weight: 0, dense_k: 4, bm25_k: 4, final_top_k: 4, reranker: "cross_encoder", top_n: 3, max_rewrite_attempts: 2 },
        created_by_user_id: 1,
        last_edit_by_user_id: null,
        created_at: "2026-06-14T12:00:00Z",
        last_updated: "2026-06-14T12:00:00Z",
        simulation_ids: [],
      },
      {
        id: 502,
        name: "BM25 CRAG",
        strategy: "crag",
        knowledge_graph_index_id: null,
        config: { bm25_weight: 1, dense_k: 4, bm25_k: 4, final_top_k: 4, reranker: "cross_encoder", top_n: 3, max_rewrite_attempts: 2 },
        created_by_user_id: 1,
        last_edit_by_user_id: null,
        created_at: "2026-06-14T12:00:00Z",
        last_updated: "2026-06-14T12:00:00Z",
        simulation_ids: [],
      },
      {
        id: 503,
        name: "Hybrid CRAG",
        strategy: "crag",
        knowledge_graph_index_id: null,
        config: { bm25_weight: 0.5, dense_k: 4, bm25_k: 4, final_top_k: 4, reranker: "cross_encoder", top_n: 3, max_rewrite_attempts: 2 },
        created_by_user_id: 1,
        last_edit_by_user_id: null,
        created_at: "2026-06-14T12:00:00Z",
        last_updated: "2026-06-14T12:00:00Z",
        simulation_ids: [],
      },
      {
        id: 501,
        name: "Contracts GraphRAG",
        strategy: "graphrag",
        knowledge_graph_index_id: 91,
        config: {
          retrieval_mode: "hybrid",
          top_k: 4,
          evidence_limit: 8,
          traversal_depth: 2,
          rrf_k: 60,
        },
        created_by_user_id: 1,
        last_edit_by_user_id: null,
        created_at: "2026-06-14T12:00:00Z",
        last_updated: "2026-06-14T12:00:00Z",
        simulation_ids: [],
      },
    ],
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/knowledgeGraphs/knowledgeGraphQueries", () => ({
  useKnowledgeGraphsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [
      {
        id: 91,
        name: "Contracts graph",
        corpus_index_id: 77,
        status: "built",
      },
    ],
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/scenarios/scenarioQueries", () => ({
  useScenariosQuery: () => ({ isLoading: false, isError: false, data: [], refetch: vi.fn() }),
}));

vi.mock("@/features/counterpartPersonas/personaQueries", () => ({
  usePersonasQuery: () => ({ isLoading: false, isError: false, data: [], refetch: vi.fn() }),
}));

vi.mock("@/features/prompts/promptQueries", () => ({
  usePromptsQuery: () => ({ isLoading: false, isError: false, data: [], refetch: vi.fn() }),
}));

vi.mock("@/features/sessions/sessionQueries", () => ({
  useSessionsQuery: () => ({ isLoading: false, isError: false, data: [], refetch: vi.fn() }),
}));

vi.mock("@/features/users/userQueries", () => ({
  useUsersQuery: () => ({ isLoading: false, isError: false, data: [], refetch: vi.fn() }),
}));

vi.mock("@/features/llmModels/llmModelQueries", () => ({
  useLlmModelCatalogQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
      providers: [
        {
          provider: "openai",
          models: [{ name: "gpt-4o-mini" }, { name: "gpt-4.1-mini" }],
        },
        {
          provider: "ollama",
          models: [{ name: "qwen2.5:3b", size_gib: 2.3 }],
        },
      ],
      gpu_memory_gib: 12,
    },
  }),
}));

describe("SimulationsPage", () => {
  beforeEach(() => {
    createSimulation.mockReset();
    navigate.mockReset();
    retrievalOptionsQueryState.isLoading = false;
    retrievalOptionsQueryState.isError = false;
    retrievalOptionsQueryState.error = null;
    retrievalOptionsQueryState.refetch.mockReset();
    retrievalOptionsQueryState.calls.length = 0;
    retrievalOptionsQueryState.responses[500] = {
      mode: "dense",
      dense_indices: [{ id: 77, name: "Index A" }],
      bm25_indices: [],
      compatible_pairs: [],
    };
    retrievalOptionsQueryState.responses[502] = {
      mode: "bm25",
      dense_indices: [],
      bm25_indices: [{ id: 88, name: "BM25 A" }],
      compatible_pairs: [],
    };
    retrievalOptionsQueryState.responses[503] = {
      mode: "hybrid",
      dense_indices: [
        { id: 77, name: "Index A" },
        { id: 78, name: "Index B" },
      ],
      bm25_indices: [
        { id: 88, name: "BM25 A" },
        { id: 89, name: "BM25 B" },
      ],
      compatible_pairs: [
        { corpus_index_id: 77, bm25_index_id: 88 },
        { corpus_index_id: 78, bm25_index_id: 89 },
      ],
    };
  });

  it("renders a required RAG profile selector in the create form", () => {
    render(<SimulationsPage />);

    expect(screen.getByRole("combobox", { name: /RAG profile/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Default CRAG" })).toBeInTheDocument();
  });

  it("locks the corpus and index to the graph bound to a GraphRAG profile", () => {
    render(<SimulationsPage />);

    fireEvent.change(screen.getByRole("combobox", { name: /RAG profile/ }), {
      target: { value: "501" },
    });

    const corpus = screen.getByRole("combobox", { name: "Corpus" });
    const corpusIndex = screen.getByRole("combobox", { name: "Corpus index" });
    expect(corpus).toHaveValue("11");
    expect(corpusIndex).toHaveValue("77");
    expect(corpus).toBeDisabled();
    expect(corpusIndex).toBeDisabled();
    expect(retrievalOptionsQueryState.calls).toContainEqual({
      corpusId: 11,
      ragProfileId: 501,
      enabled: false,
    });
  });

  it("renders only the artifact selectors required by the selected CRAG mode", () => {
    render(<SimulationsPage />);
    fireEvent.change(screen.getByRole("combobox", { name: "Corpus" }), { target: { value: "11" } });

    fireEvent.change(screen.getByRole("combobox", { name: /RAG profile/ }), { target: { value: "502" } });
    expect(screen.getByRole("combobox", { name: /^BM25 index/ })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Corpus index" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: /RAG profile/ }), { target: { value: "503" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Corpus index" }), { target: { value: "77" } });
    expect(screen.getByRole("combobox", { name: /^BM25 index/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "BM25 A" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "BM25 B" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: /RAG profile/ }), { target: { value: "500" } });
    expect(screen.getByRole("combobox", { name: "Corpus index" })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /^BM25 index/ })).not.toBeInTheDocument();
  });

  it("starts hybrid selection from either artifact dropdown", async () => {
    const user = userEvent.setup();
    render(<SimulationsPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "503");

    expect(screen.getByRole("option", { name: "Index A" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Index B" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "BM25 A" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "BM25 B" })).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: /^BM25 index/ }), "89");

    expect(screen.queryByRole("option", { name: "Index A" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Index B" })).toBeInTheDocument();
  });

  it("submits only a BM25 binding for a BM25-only profile", async () => {
    createSimulation.mockResolvedValueOnce({ id: 46 });
    const user = userEvent.setup();
    render(<SimulationsPage />);

    await user.type(screen.getByLabelText("Name"), "BM25 simulation");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "502");
    await user.selectOptions(screen.getByRole("combobox", { name: /^BM25 index/ }), "88");
    await user.click(screen.getByRole("button", { name: "Create simulation" }));

    expect(createSimulation).toHaveBeenCalledWith(
      expect.objectContaining({ corpus_index_id: null, bm25_index_id: 88, rag_profile_id: 502 }),
    );
  });

  it("submits both compatible bindings for a hybrid profile", async () => {
    createSimulation.mockResolvedValueOnce({ id: 47 });
    const user = userEvent.setup();
    render(<SimulationsPage />);

    await user.type(screen.getByLabelText("Name"), "Hybrid simulation");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "503");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus index" }), "77");
    await user.selectOptions(screen.getByRole("combobox", { name: /^BM25 index/ }), "88");
    await user.click(screen.getByRole("button", { name: "Create simulation" }));

    expect(createSimulation).toHaveBeenCalledWith(
      expect.objectContaining({ corpus_index_id: 77, bm25_index_id: 88, rag_profile_id: 503 }),
    );
  });

  it("distinguishes BM25 loading from an empty artifact list", () => {
    retrievalOptionsQueryState.isLoading = true;
    render(<SimulationsPage />);
    fireEvent.change(screen.getByRole("combobox", { name: "Corpus" }), { target: { value: "11" } });
    fireEvent.change(screen.getByRole("combobox", { name: /RAG profile/ }), { target: { value: "502" } });

    expect(screen.getByText("Loading retrieval options...")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /^BM25 index/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create simulation" })).toBeDisabled();
    expect(screen.queryByText(/built BM25 artifact is required/)).not.toBeInTheDocument();
  });

  it("shows an actionable BM25 request error", async () => {
    retrievalOptionsQueryState.isError = true;
    retrievalOptionsQueryState.error = new Error("Retrieval service unavailable");
    const user = userEvent.setup();
    render(<SimulationsPage />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "502");

    expect(screen.getByRole("alert")).toHaveTextContent("Retrieval service unavailable");
    expect(screen.getByRole("combobox", { name: /^BM25 index/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create simulation" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Retry retrieval options" }));
    expect(retrievalOptionsQueryState.refetch).toHaveBeenCalledTimes(1);
  });

  it.each([
    [500, "A built dense index is required."],
    [502, "A built BM25 artifact is required."],
    [503, "No compatible dense/BM25 pair exists."],
  ])("explains an empty retrieval response for profile %s", async (profileId, copy) => {
    retrievalOptionsQueryState.responses[profileId] = {
      mode: profileId === 500 ? "dense" : profileId === 502 ? "bm25" : "hybrid",
      dense_indices: [],
      bm25_indices: [],
      compatible_pairs: [],
    };
    const user = userEvent.setup();
    render(<SimulationsPage />);

    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(
      screen.getByRole("combobox", { name: /RAG profile/ }),
      String(profileId),
    );

    expect(screen.getByText(copy)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create simulation" })).toBeDisabled();
  });

  it("refetches and reconciles selections after a stale create conflict", async () => {
    createSimulation.mockRejectedValueOnce(
      new ApiError(
        "Unable to create simulation",
        409,
        { detail: "Hybrid indexes must contain the same chunk set" },
      ),
    );
    retrievalOptionsQueryState.refetch.mockImplementationOnce(async () => {
      retrievalOptionsQueryState.responses[503] = {
        mode: "hybrid",
        dense_indices: [{ id: 78, name: "Index B" }],
        bm25_indices: [{ id: 89, name: "BM25 B" }],
        compatible_pairs: [{ corpus_index_id: 78, bm25_index_id: 89 }],
      };
      return { data: retrievalOptionsQueryState.responses[503] };
    });
    const user = userEvent.setup();
    const { rerender } = render(<SimulationsPage />);

    await user.type(screen.getByLabelText("Name"), "Stale hybrid simulation");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "503");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus index" }), "77");
    await user.selectOptions(screen.getByRole("combobox", { name: /^BM25 index/ }), "88");
    await user.click(screen.getByRole("button", { name: "Create simulation" }));

    expect(await screen.findByText("Hybrid indexes must contain the same chunk set")).toBeInTheDocument();
    expect(retrievalOptionsQueryState.refetch).toHaveBeenCalledTimes(1);
    expect(navigate).not.toHaveBeenCalled();

    rerender(<SimulationsPage />);
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: "Corpus index" })).toHaveValue("");
      expect(screen.getByRole("combobox", { name: /^BM25 index/ })).toHaveValue("");
    });
  });

  it("keeps the corpus index selector bordered, single-line, and top aligned with description", () => {
    render(<SimulationsPage />);

    fireEvent.change(screen.getByRole("combobox", { name: "Corpus" }), { target: { value: "11" } });
    fireEvent.change(screen.getByRole("combobox", { name: /RAG profile/ }), { target: { value: "500" } });

    const corpusIndex = screen.getByRole("combobox", { name: "Corpus index" });

    expect(corpusIndex).toHaveClass("border");
    expect(corpusIndex).toHaveClass("border-slate-300");
    expect(corpusIndex).toHaveClass("min-h-10");
    expect(corpusIndex).toHaveClass("leading-5");
    expect(corpusIndex.closest("label")).toHaveClass("self-start");
  });

  it("keeps the scenario selector top aligned and the same height style as RAG profile", () => {
    render(<SimulationsPage />);

    const ragProfile = screen.getByRole("combobox", { name: /RAG profile/ });
    const scenario = screen.getByRole("combobox", { name: "Scenario" });

    expect(scenario.className).toBe(ragProfile.className);
    expect(scenario.closest("label")).toHaveClass("self-start");
  });

  it("reveals learner agent model and search controls when enabled", async () => {
    const user = userEvent.setup();
    render(<SimulationsPage />);

    expect(screen.getByRole("checkbox", { name: "Use Learning Agent" })).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Learner response LLM" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Use Learning Agent" }));

    expect(screen.getByRole("combobox", { name: "Learner response LLM" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Negotiation summary LLM" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Tavily summary LLM" })).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Tavily max results" })).toHaveValue(5);
    expect(screen.getByRole("checkbox", { name: "Include Tavily images" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Include Tavily answer" })).toBeInTheDocument();
  });

  it("submits learner configuration when enabled", async () => {
    createSimulation.mockResolvedValueOnce({ id: 44 });
    const user = userEvent.setup();
    render(<SimulationsPage />);

    await user.type(screen.getByLabelText("Name"), "Salary practice");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "500");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus index" }), "77");
    await user.click(screen.getByRole("checkbox", { name: "Use Learning Agent" }));
    const modelSelectors = screen.getAllByRole("combobox", { name: "Model" });
    await user.selectOptions(modelSelectors[0], "gpt-4.1-mini");
    await user.selectOptions(modelSelectors[1], "gpt-4.1-mini");
    await user.selectOptions(modelSelectors[2], "gpt-4o-mini");
    await user.clear(screen.getByRole("spinbutton", { name: "Tavily max results" }));
    await user.type(screen.getByRole("spinbutton", { name: "Tavily max results" }), "7");
    await user.click(screen.getByRole("checkbox", { name: "Include Tavily images" }));
    await user.click(screen.getByRole("checkbox", { name: "Include Tavily answer" }));
    await user.click(screen.getByRole("button", { name: "Create simulation" }));

    expect(createSimulation).toHaveBeenCalledWith(
      expect.objectContaining({
        use_learner_agent: true,
        learner_response_llm_provider: "openai",
        learner_response_llm_model: "gpt-4.1-mini",
        learner_summary_llm_provider: "openai",
        learner_summary_llm_model: "gpt-4.1-mini",
        learner_tavily_summary_llm_provider: "openai",
        learner_tavily_summary_llm_model: "gpt-4o-mini",
        learner_tavily_max_results: 7,
        learner_tavily_include_images: true,
        learner_tavily_include_answers: true,
      }),
    );
  });

  it("submits learner disabled when unchecked", async () => {
    createSimulation.mockResolvedValueOnce({ id: 45 });
    const user = userEvent.setup();
    render(<SimulationsPage />);

    await user.type(screen.getByLabelText("Name"), "Salary practice");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus" }), "11");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "500");
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus index" }), "77");
    await user.click(screen.getByRole("button", { name: "Create simulation" }));

    expect(createSimulation).toHaveBeenCalledWith(
      expect.objectContaining({
        use_learner_agent: false,
      }),
    );
    expect(createSimulation.mock.calls[0][0]).not.toHaveProperty("learner_response_llm_model");
  });
});
