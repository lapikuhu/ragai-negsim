import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IndexingPage } from "./IndexingPage";

const queryState = vi.hoisted(() => ({
  activeJob: null as any,
  jobs: [] as any[],
  selectedJobDetail: null as any,
}));

vi.mock("@/features/corpora/corpusQueries", () => ({
  useCorporaQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn()
  })
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useChunkingProfilesQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn()
  }),
  useCorpusIndicesQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn()
  }),
  useEmbeddingModelsQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn()
  }),
  useVectorStoresQuery: () => ({
    isLoading: false,
    isError: false,
    data: [],
    refetch: vi.fn()
  }),
}));

vi.mock("@/features/indexing/indexingQueries", () => ({
  useActiveIndexingJobQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.activeJob,
    refetch: vi.fn()
  }),
  useIndexingJobsQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.jobs,
    refetch: vi.fn()
  }),
  useIndexingJobDetailQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.selectedJobDetail,
    refetch: vi.fn()
  }),
  useCreateIndexingJobMutation: () => ({
    isPending: false,
    mutateAsync: vi.fn()
  }),
  useCancelIndexingJobMutation: () => ({
    isPending: false,
    mutateAsync: vi.fn()
  }),
}));

describe("IndexingPage", () => {
  beforeEach(() => {
    queryState.activeJob = null;
    queryState.selectedJobDetail = null;
    queryState.jobs = [];
  });

  it("shows the active job in the main card even when a historical detail is selected", () => {
    queryState.activeJob = {
      id: 77,
      requested_index_name: "active-index",
      status: "running",
      stage: "cleaning",
      queued_at: "2026-06-12T10:00:00Z",
      completed_at: null,
      processed_documents: 1,
      total_documents: 3,
      chunks_created: 0,
      chunks_indexed: 0,
      current_document_name: "active.pdf",
      warnings: []
    };
    queryState.selectedJobDetail = {
      id: 12,
      requested_index_name: "historical-index",
      status: "completed",
      stage: "finished",
      queued_at: "2026-06-11T10:00:00Z",
      completed_at: "2026-06-11T10:10:00Z",
      processed_documents: 3,
      total_documents: 3,
      chunks_created: 20,
      chunks_indexed: 20,
      current_document_name: null,
      warnings: []
    };

    render(<IndexingPage />);

    expect(screen.getByText("active-index")).toBeInTheDocument();
    expect(screen.queryByText("historical-index")).not.toBeInTheDocument();
    expect(screen.getByText("active.pdf")).toBeInTheDocument();
  });

  it("shows an embedding-specific current activity message once document ingestion is finished", () => {
    queryState.activeJob = {
      id: 77,
      requested_index_name: "active-index",
      status: "running",
      stage: "embedding",
      queued_at: "2026-06-12T10:00:00Z",
      completed_at: null,
      processed_documents: 3,
      total_documents: 3,
      chunks_created: 42,
      chunks_indexed: 10,
      current_document_name: null,
      warnings: []
    };

    render(<IndexingPage />);

    expect(screen.getByText("All documents ingested. Embedding chunks now.")).toBeInTheDocument();
  });
});
