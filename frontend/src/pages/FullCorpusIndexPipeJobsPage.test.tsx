import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FullCorpusIndexPipeJobsPage } from "./FullCorpusIndexPipeJobsPage";

const queryState = vi.hoisted(() => ({
  activeJob: null as any,
  jobs: [] as any[],
  selectedJobDetail: null as any,
  bm25Child: null as any,
  createJob: vi.fn(),
  chunkSetNameAvailability: vi.fn(),
}));

vi.mock("@/features/corpora/corpusQueries", () => ({
  useCorporaQuery: () => ({
    isLoading: false,
    isError: false,
    data: [{ id: 1, name: "Policies" }],
    refetch: vi.fn()
  })
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useChunkingProfilesQuery: () => ({
    isLoading: false,
    isError: false,
    data: [{ id: 2, name: "Recursive" }],
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
    data: [{ name: "mini-l6-v2", display_name: "Mini", dimensionality: 384 }],
    refetch: vi.fn()
  }),
  useVectorStoresQuery: () => ({
    isLoading: false,
    isError: false,
    data: [{ id: 3, name: "Local", embedding_dimensions: 384 }],
    refetch: vi.fn()
  }),
}));

vi.mock("@/features/corpusBm25BuildJobs/corpusBm25BuildJobQueries", () => ({
  useCorpusBm25BuildJobQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.bm25Child,
    refetch: vi.fn(),
  }),
  useCorpusChunkSetNameAvailabilityQuery: (
    corpusId: number,
    name: string,
    enabled?: boolean,
  ) => queryState.chunkSetNameAvailability(corpusId, name, enabled),
}));

vi.mock("@/features/fullCorpusIndexPipeJobs/fullCorpusIndexPipeJobQueries", () => ({
  useActiveFullCorpusIndexPipeJobQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.activeJob,
    refetch: vi.fn()
  }),
  useFullCorpusIndexPipeJobsQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.jobs,
    refetch: vi.fn()
  }),
  useFullCorpusIndexPipeJobDetailQuery: () => ({
    isLoading: false,
    isError: false,
    data: queryState.selectedJobDetail,
    refetch: vi.fn()
  }),
  useCreateFullCorpusIndexPipeJobMutation: () => ({
    isPending: false,
    mutateAsync: queryState.createJob
  }),
  useCancelFullCorpusIndexPipeJobMutation: () => ({
    isPending: false,
    mutateAsync: vi.fn()
  }),
}));

describe("FullCorpusIndexPipeJobsPage", () => {
  beforeEach(() => {
    queryState.activeJob = null;
    queryState.selectedJobDetail = null;
    queryState.jobs = [];
    queryState.bm25Child = null;
    queryState.createJob.mockReset();
    queryState.createJob.mockResolvedValue({ id: 99 });
    queryState.chunkSetNameAvailability.mockReset();
    queryState.chunkSetNameAvailability.mockImplementation(
      (_corpusId: number, _name: string, enabled = true) => ({
        data: enabled
          ? queryState.activeJob
            ? {
                available: false,
                reason: "Corpus chunk set name already exists or is reserved",
              }
            : { available: true }
          : undefined,
        isLoading: false,
      }),
    );
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

    render(<FullCorpusIndexPipeJobsPage />);

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

    render(<FullCorpusIndexPipeJobsPage />);

    expect(screen.getByText("All documents ingested. Embedding chunks now.")).toBeInTheDocument();
  });

  it("keeps the Corpus dropdown aligned with the Chunking profile dropdown", () => {
    render(<FullCorpusIndexPipeJobsPage />);

    const corpusField = screen.getByLabelText("Corpus").closest("label");
    const chunkingProfileField = screen.getByLabelText(/Chunking profile/).closest("label");

    expect(corpusField).not.toBeNull();
    expect(chunkingProfileField).not.toBeNull();
    expect(corpusField).toHaveClass("content-start");
    expect(chunkingProfileField).toHaveClass("content-start");
  });

  it("defaults to a required, user-named BM25 index and submits the pair", async () => {
    const user = userEvent.setup();
    render(<FullCorpusIndexPipeJobsPage />);

    const checkbox = screen.getByRole("checkbox", { name: "Build BM25 index also" });
    expect(checkbox).toBeChecked();
    expect(screen.getByLabelText(/^BM25 index name/)).toBeRequired();

    await user.selectOptions(screen.getByLabelText("Corpus"), "1");
    await user.selectOptions(screen.getByLabelText(/Chunking profile/), "2");
    await user.selectOptions(screen.getByLabelText("Embedding model"), "mini-l6-v2");
    await user.selectOptions(screen.getByLabelText("Vector store"), "3");
    await user.type(screen.getByLabelText(/^Index name/), "policy dense");
    await user.type(screen.getByLabelText(/^Chunk set name/), "August set");
    await user.type(screen.getByLabelText(/^BM25 index name/), "  policy lexical  ");
    await user.click(screen.getByRole("button", { name: "Index corpus" }));

    expect(queryState.createJob).toHaveBeenCalledWith(
      expect.objectContaining({
        build_bm25: true,
        requested_index_name: "policy dense",
        requested_chunk_set_name: "August set",
        requested_bm25_index_name: "policy lexical",
      }),
    );
  });

  it("allows an explicit dense-only submission without a BM25 name", async () => {
    const user = userEvent.setup();
    render(<FullCorpusIndexPipeJobsPage />);

    await user.click(screen.getByRole("checkbox", { name: "Build BM25 index also" }));
    expect(screen.queryByLabelText(/^BM25 index name/)).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Corpus"), "1");
    await user.selectOptions(screen.getByLabelText(/Chunking profile/), "2");
    await user.selectOptions(screen.getByLabelText("Embedding model"), "mini-l6-v2");
    await user.selectOptions(screen.getByLabelText("Vector store"), "3");
    await user.type(screen.getByLabelText(/^Index name/), "policy dense");
    await user.type(screen.getByLabelText(/^Chunk set name/), "August set");
    await user.click(screen.getByRole("button", { name: "Index corpus" }));

    expect(queryState.createJob).toHaveBeenCalledWith(
      expect.objectContaining({
        build_bm25: false,
        requested_bm25_index_name: null,
      }),
    );
  });

  it("stops chunk-set availability checks after queueing locks the form", async () => {
    const user = userEvent.setup();
    queryState.createJob.mockImplementation(async () => {
      queryState.activeJob = {
        id: 99,
        requested_index_name: "policy dense",
        requested_chunk_set_name: "August set",
        build_bm25: false,
        status: "queued",
        stage: "validating",
        queued_at: "2026-08-16T12:00:00Z",
        completed_at: null,
        processed_documents: 0,
        total_documents: 1,
        chunks_created: 0,
        chunks_indexed: 0,
        current_document_name: null,
        warnings: [],
      };
      return { id: 99 };
    });
    render(<FullCorpusIndexPipeJobsPage />);

    await user.click(screen.getByRole("checkbox", { name: "Build BM25 index also" }));
    await user.selectOptions(screen.getByLabelText("Corpus"), "1");
    await user.selectOptions(screen.getByLabelText(/Chunking profile/), "2");
    await user.selectOptions(screen.getByLabelText("Embedding model"), "mini-l6-v2");
    await user.selectOptions(screen.getByLabelText("Vector store"), "3");
    await user.type(screen.getByLabelText(/^Index name/), "policy dense");
    await user.type(screen.getByLabelText(/^Chunk set name/), "August set");
    await user.click(screen.getByRole("button", { name: "Index corpus" }));

    expect(await screen.findByText(/Queued full corpus index pipe job #99/)).toBeInTheDocument();
    expect(queryState.chunkSetNameAvailability).toHaveBeenLastCalledWith(
      1,
      "August set",
      false,
    );
    expect(
      screen.queryByText("Corpus chunk set name already exists or is reserved"),
    ).not.toBeInTheDocument();
  });

  it("shows the linked BM25 child and rollback activity", () => {
    queryState.activeJob = {
      id: 77,
        requested_index_name: "policy dense",
        requested_chunk_set_name: "August set",
      requested_bm25_index_name: "policy lexical",
      build_bm25: true,
      bm25_build_job_id: 91,
      status: "running",
      stage: "rolling_back",
      queued_at: "2026-06-12T10:00:00Z",
      completed_at: null,
      processed_documents: 3,
      total_documents: 3,
      chunks_created: 42,
      chunks_indexed: 10,
      current_document_name: null,
      warnings: [],
    };
    queryState.bm25Child = { id: 91, status: "failed", failure_detail: "Rolled back" };

    render(<FullCorpusIndexPipeJobsPage />);

    expect(screen.getByText("policy lexical")).toBeInTheDocument();
    expect(screen.getByText("BM25 job #91")).toBeInTheDocument();
    expect(screen.getByText("Cleaning up BM25 and dense artifacts before the job is marked terminal.")).toBeInTheDocument();
  });
});
