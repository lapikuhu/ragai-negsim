import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimulationsPage } from "./SimulationsPage";

const createSimulation = vi.fn();
const navigate = vi.fn();

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
    data: [{ id: 77, corpus_id: 11, name: "Index A" }],
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
        config: { top_k: 4, reranker: "cross_encoder", top_n: 3, max_rewrite_attempts: 2 },
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
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus index" }), "77");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "500");
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
    await user.selectOptions(screen.getByRole("combobox", { name: "Corpus index" }), "77");
    await user.selectOptions(screen.getByRole("combobox", { name: /RAG profile/ }), "500");
    await user.click(screen.getByRole("button", { name: "Create simulation" }));

    expect(createSimulation).toHaveBeenCalledWith(
      expect.objectContaining({
        use_learner_agent: false,
      }),
    );
    expect(createSimulation.mock.calls[0][0]).not.toHaveProperty("learner_response_llm_model");
  });
});
