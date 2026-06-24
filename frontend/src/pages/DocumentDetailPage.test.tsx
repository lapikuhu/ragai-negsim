import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentDetailPage } from "./DocumentDetailPage";

const state = vi.hoisted(() => ({
  query: {
    isLoading: false,
    isError: false,
    data: {
      id: 7,
      name: "Negotiation brief",
      description: "Detail test document",
      source_path: "app/raw_docs_store/brief.pdf",
      source_hash: "abc123",
      source_size: 2048,
      source_mtime: "2026-06-24T10:00:00Z",
      source_status: "available",
      uploaded_at: "2026-06-24T10:05:00Z",
      uploaded_by_user_id: 12,
      uploaded_by_username: "teacher" as string | null,
      parsed_at: null
    },
    error: null as Error | null,
    refetch: vi.fn()
  },
  profiles: {
    data: [],
  },
  ingestMutation: {
    isPending: false,
    mutateAsync: vi.fn()
  },
  chunkMutation: {
    isPending: false,
    mutateAsync: vi.fn()
  }
}));

vi.mock("react-router-dom", () => ({
  useParams: () => ({ documentId: "7" })
}));

vi.mock("@/features/documents/documentQueries", () => ({
  useDocumentDetailQuery: () => state.query,
  useIngestDocumentMutation: () => state.ingestMutation,
  useChunkDocumentMutation: () => state.chunkMutation
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useChunkingProfilesQuery: () => ({
    isLoading: false,
    isError: false,
    data: state.profiles.data,
    refetch: vi.fn()
  })
}));

describe("DocumentDetailPage", () => {
  beforeEach(() => {
    state.query.isLoading = false;
    state.query.isError = false;
    state.query.error = null;
    state.query.data = {
      id: 7,
      name: "Negotiation brief",
      description: "Detail test document",
      source_path: "app/raw_docs_store/brief.pdf",
      source_hash: "abc123",
      source_size: 2048,
      source_mtime: "2026-06-24T10:00:00Z",
      source_status: "available",
      uploaded_at: "2026-06-24T10:05:00Z",
      uploaded_by_user_id: 12,
      uploaded_by_username: "teacher" as string | null,
      parsed_at: null
    };
  });

  it("shows the uploader username when the API provides it", () => {
    render(<DocumentDetailPage />);

    expect(screen.getByText("teacher")).toBeInTheDocument();
    expect(screen.queryByText(/^12$/)).not.toBeInTheDocument();
  });

  it("falls back to the uploader id when username is missing", () => {
    state.query.data = {
      ...state.query.data,
      uploaded_by_username: null
    };

    render(<DocumentDetailPage />);

    expect(screen.getByText("12")).toBeInTheDocument();
  });
});
