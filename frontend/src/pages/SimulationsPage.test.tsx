import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

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

describe("SimulationsPage", () => {
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
});
