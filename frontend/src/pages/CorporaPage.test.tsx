import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import type { RawDocumentRead } from "@/api/types";
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
    data: [] as RawDocumentRead[],
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
    state.documentsQuery.isLoading = false;
    state.documentsQuery.isError = false;
    state.documentsQuery.error = null;
    state.documentsQuery.data = [];
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

  it("keeps the Name field aligned with the Raw documents field", () => {
    render(
      <MemoryRouter>
        <CorporaPage />
      </MemoryRouter>
    );

    const nameField = screen.getByLabelText("Name").closest("label");
    const rawDocumentsField = screen.getByText("Raw documents").closest("label");

    expect(nameField).not.toBeNull();
    expect(rawDocumentsField).not.toBeNull();
    expect(nameField).toHaveClass("content-start");
    expect(rawDocumentsField).toHaveClass("content-start");
  });

  it("shows each document title and basename in the picker", async () => {
    const user = userEvent.setup();
    state.documentsQuery.data = [
      {
        id: 42,
        name: "internal-negotiation-brief",
        description: "Course material",
        document_title: "Negotiation briefing",
        source_path: "C:\\uploads\\spring\\negotiation-brief.pdf",
        source_status: "available",
        uploaded_at: "2026-06-24T10:00:00Z",
        uploaded_by_user_id: 1
      }
    ];

    render(
      <MemoryRouter>
        <CorporaPage />
      </MemoryRouter>
    );

    await user.click(screen.getByText("Select raw documents").closest("button")!);

    expect(screen.getByText("Negotiation briefing")).toBeInTheDocument();
    expect(screen.getByText("negotiation-brief.pdf")).toBeInTheDocument();
    expect(screen.queryByText("internal-negotiation-brief")).not.toBeInTheDocument();
  });

  it("uses a clear title fallback and searches by title or filename", async () => {
    const user = userEvent.setup();
    state.documentsQuery.data = [
      {
        id: 42,
        name: "internal-negotiation-brief",
        description: null,
        document_title: "Negotiation briefing",
        source_path: "/uploads/spring/negotiation-brief.pdf",
        source_status: "available",
        uploaded_at: "2026-06-24T10:00:00Z",
        uploaded_by_user_id: 1
      },
      {
        id: 43,
        name: "internal-memo",
        description: null,
        document_title: null,
        source_path: "/uploads/spring/settlement-memo.pdf",
        source_status: "available",
        uploaded_at: "2026-06-24T10:00:00Z",
        uploaded_by_user_id: 1
      }
    ];

    render(
      <MemoryRouter>
        <CorporaPage />
      </MemoryRouter>
    );

    await user.click(screen.getByText("Select raw documents").closest("button")!);
    expect(screen.getByText("Not available")).toBeInTheDocument();

    const search = screen.getByPlaceholderText(/search by title/i);
    await user.type(search, "briefing");
    expect(screen.getByText("Negotiation briefing")).toBeInTheDocument();
    expect(screen.queryByText("settlement-memo.pdf")).not.toBeInTheDocument();

    await user.clear(search);
    await user.type(search, "settlement-memo.pdf");
    expect(screen.getByText("settlement-memo.pdf")).toBeInTheDocument();
    expect(screen.queryByText("Negotiation briefing")).not.toBeInTheDocument();
  });
});
