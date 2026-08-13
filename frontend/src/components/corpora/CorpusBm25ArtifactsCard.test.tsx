import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CorpusBm25ArtifactsCard } from "./CorpusBm25ArtifactsCard";

const state = vi.hoisted(() => ({
  artifacts: { data: [] as any[], isLoading: false, isError: false, error: null, refetch: vi.fn() },
  chunkSets: { data: [] as any[], isLoading: false, isError: false, error: null, refetch: vi.fn() },
  jobs: { data: [] as any[], isLoading: false, isError: false, error: null, refetch: vi.fn() },
  queue: { mutateAsync: vi.fn(), isPending: false },
  cancel: { mutateAsync: vi.fn(), isPending: false },
  retry: { mutateAsync: vi.fn(), isPending: false },
}));

vi.mock("@/features/corpusBm25Indices/corpusBm25IndexQueries", () => ({
  useCorpusBm25IndicesQuery: () => state.artifacts,
}));
vi.mock("@/features/corpusBm25BuildJobs/corpusBm25BuildJobQueries", () => ({
  useCorpusChunkSetsQuery: () => state.chunkSets,
  useCorpusBm25BuildJobsQuery: () => state.jobs,
  useQueueCorpusBm25BuildJobMutation: () => state.queue,
  useCancelCorpusBm25BuildJobMutation: () => state.cancel,
  useRetryCorpusBm25BuildJobMutation: () => state.retry,
}));

function renderCard() {
  return render(<MemoryRouter><CorpusBm25ArtifactsCard corpusId={11} corpusName="Policy" /></MemoryRouter>);
}

describe("CorpusBm25ArtifactsCard", () => {
  beforeEach(() => {
    state.artifacts.data = [];
    state.chunkSets.data = [];
    state.jobs.data = [];
    vi.clearAllMocks();
  });

  it("lists multiple artifacts and keeps the build action available", () => {
    state.artifacts.data = [
      { id: 31, name: "recursive bm25", status: "built", chunking_profile_id: 3, document_count: 8, document_chunk_ids_checksum: "a".repeat(64), created_at: "2026-08-13T10:00:00Z" },
      { id: 32, name: "semantic bm25", status: "built", chunking_profile_id: 4, document_count: 6, document_chunk_ids_checksum: "b".repeat(64), created_at: "2026-08-13T10:00:00Z" },
    ];
    renderCard();
    expect(screen.getByText("recursive bm25")).toBeInTheDocument();
    expect(screen.getByText("semantic bm25")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Build BM25 artifact" })).toBeEnabled();
  });

  it("requires explicit chunk-set selection", async () => {
    state.chunkSets.data = [
      { chunking_profile_id: 3, chunking_profile_name: "recursive", distinct_document_count: 2, chunk_count: 8, document_chunk_ids_checksum: "a".repeat(64) },
      { chunking_profile_id: 4, chunking_profile_name: "semantic", distinct_document_count: 2, chunk_count: 6, document_chunk_ids_checksum: "b".repeat(64) },
    ];
    renderCard();
    await userEvent.click(screen.getByRole("button", { name: "Build BM25 artifact" }));
    expect(screen.getByRole("combobox", { name: "Chunk set" })).toHaveValue("");
    expect(screen.getByRole("button", { name: "Queue BM25 build" })).toBeDisabled();
  });

  it("directs an unchunked corpus to the full pipeline", async () => {
    renderCard();
    await userEvent.click(screen.getByRole("button", { name: "Build BM25 artifact" }));
    expect(screen.getByText(/BM25 requires persisted chunks/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Full Corpus Index Pipe" })).toHaveAttribute("href", "/full-corpus-index-pipe-jobs");
  });
});
