import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { CorporaPage } from "./CorporaPage";

const state = vi.hoisted(() => ({
  corporaQuery: {
    isLoading: false,
    isError: false,
    data: [
      {
        id: 11,
        name: "alpha corpus",
        description: "Corpus list test",
        created_by_user_id: 1,
        created_by_username: "teacher" as string | null,
        created_at: "2026-06-24T10:00:00Z"
      }
    ],
    error: null as Error | null,
    refetch: vi.fn()
  },
  documentsQuery: {
    isLoading: false,
    isError: false,
    data: [],
    error: null as Error | null,
    refetch: vi.fn()
  },
  indicesQuery: {
    data: []
  },
  profilesQuery: {
    data: []
  },
  vectorStoresQuery: {
    data: []
  },
  createMutation: {
    isPending: false,
    mutateAsync: vi.fn()
  }
}));

vi.mock("@/features/corpora/corpusQueries", () => ({
  useCorporaQuery: () => state.corporaQuery,
  useCreateCorpusMutation: () => state.createMutation
}));

vi.mock("@/features/documents/documentQueries", () => ({
  useDocumentsQuery: () => state.documentsQuery
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useChunkingProfilesQuery: () => state.profilesQuery,
  useCorpusIndicesQuery: () => state.indicesQuery,
  useVectorStoresQuery: () => state.vectorStoresQuery
}));

describe("CorporaPage", () => {
  beforeEach(() => {
    state.corporaQuery.isLoading = false;
    state.corporaQuery.isError = false;
    state.corporaQuery.error = null;
    state.corporaQuery.data = [
      {
        id: 11,
        name: "alpha corpus",
        description: "Corpus list test",
        created_by_user_id: 1,
        created_by_username: "teacher" as string | null,
        created_at: "2026-06-24T10:00:00Z"
      }
    ];
  });

  it("shows creator usernames in the corpora list when the API provides them", () => {
    render(
      <MemoryRouter>
        <CorporaPage />
      </MemoryRouter>
    );

    expect(screen.getByText("teacher")).toBeInTheDocument();
    expect(screen.queryByText(/^1$/)).not.toBeInTheDocument();
  });

  it("falls back to creator ids when usernames are missing", () => {
    state.corporaQuery.data = [
      {
        ...state.corporaQuery.data[0],
        created_by_username: null
      }
    ];

    render(
      <MemoryRouter>
        <CorporaPage />
      </MemoryRouter>
    );

    expect(screen.getByText("1")).toBeInTheDocument();
  });
});
