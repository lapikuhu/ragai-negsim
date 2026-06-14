import { render, screen } from "@testing-library/react";
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
        config: { top_k: 4, reranker: "cross_encoder", top_n: 3, max_rewrite_attempts: 2 },
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
});
