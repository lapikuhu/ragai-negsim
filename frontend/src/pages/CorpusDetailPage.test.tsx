import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CorpusDetailPage } from "./CorpusDetailPage";

const state = vi.hoisted(() => ({
  corporaQuery: {
    isLoading: false,
    isError: false,
    data: [
      {
        id: 11,
        name: "alpha corpus",
        description: "Corpus detail test",
        created_by_user_id: 1,
        created_by_username: "teacher" as string | null,
        last_edit_by_user_id: 2,
        last_edit_by_username: "coach" as string | null,
        created_at: "2026-06-24T10:00:00Z"
      }
    ],
    error: null as Error | null,
    refetch: vi.fn()
  },
  indicesQuery: {
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn()
  }
}));

vi.mock("react-router-dom", () => ({
  useParams: () => ({ corpusId: "11" })
}));

vi.mock("@/features/corpora/corpusQueries", () => ({
  useCorporaQuery: () => state.corporaQuery
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useCorpusIndicesQuery: () => state.indicesQuery
}));

describe("CorpusDetailPage", () => {
  beforeEach(() => {
    state.corporaQuery.isLoading = false;
    state.corporaQuery.isError = false;
    state.corporaQuery.error = null;
    state.corporaQuery.data = [
      {
        id: 11,
        name: "alpha corpus",
        description: "Corpus detail test",
        created_by_user_id: 1,
        created_by_username: "teacher" as string | null,
        last_edit_by_user_id: 2,
        last_edit_by_username: "coach" as string | null,
        created_at: "2026-06-24T10:00:00Z"
      }
    ];
    state.indicesQuery.data = [];
  });

  it("shows creator and editor usernames when the API provides them", () => {
    render(<CorpusDetailPage />);

    expect(screen.getByText("teacher")).toBeInTheDocument();
    expect(screen.getByText("coach")).toBeInTheDocument();
    expect(screen.queryByText(/^1$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^2$/)).not.toBeInTheDocument();
  });

  it("falls back to ids when usernames are missing", () => {
    state.corporaQuery.data = [
      {
        ...state.corporaQuery.data[0],
        created_by_username: null,
        last_edit_by_username: null
      }
    ];

    render(<CorpusDetailPage />);

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});
