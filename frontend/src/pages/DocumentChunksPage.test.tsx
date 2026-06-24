import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as documentChunkQueries from "@/features/documentChunks/documentChunkQueries";

import { DocumentChunksPage, getViewportBoundedTooltipPosition } from "./DocumentChunksPage";

function renderPage(initialEntry = "/document-chunks") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <DocumentChunksPage />
    </MemoryRouter>
  );
}

describe("DocumentChunksPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders an empty state when there are no document chunks", () => {
    vi.spyOn(documentChunkQueries, "useDocumentChunksQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [], skip: 0, limit: 20, total: 0, has_more: false },
      error: null,
      refetch: vi.fn()
    } as never);

    renderPage();

    expect(screen.getByText("No document chunks")).toBeInTheDocument();
  });

  it("renders document chunk content between metadata and created columns with a tooltip", () => {
    const content = "secret chunk body\nsecond line\nthird line\nfourth hidden line";
    vi.spyOn(documentChunkQueries, "useDocumentChunksQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        items: [
          {
            id: 5,
            raw_document_id: 11,
            raw_document_name: "Negotiation PDF",
            chunking_profile_id: 3,
            chunking_profile_name: "Recursive 1k",
            chunking_strategy: "recursive",
            chunk_index: 2,
            indexing_job_id: 77,
            content,
            chunk_metadata: { page: 4 },
            corpus_index_ids: [9, 10],
            indexed_count: 2,
            is_indexed: true,
            created_at: "2026-06-01T00:00:00Z",
            last_updated: "2026-06-02T00:00:00Z"
          }
        ],
        skip: 0,
        limit: 20,
        total: 1,
        has_more: false
      },
      error: null,
      refetch: vi.fn()
    } as never);

    renderPage();

    expect(screen.getByText("Negotiation PDF")).toBeInTheDocument();
    expect(screen.getByText("Recursive 1k")).toBeInTheDocument();
    expect(screen.getByText("recursive")).toBeInTheDocument();
    expect(screen.getByText("2 indexed")).toBeInTheDocument();

    const headers = screen.getAllByRole("columnheader").map((header) => header.textContent);
    expect(headers.slice(headers.indexOf("Metadata"), headers.indexOf("Created") + 1)).toEqual([
      "Metadata",
      "Content",
      "Created"
    ]);

    const preview = screen.getByRole("note", { name: `Chunk content: ${content}` });
    expect(preview).toHaveStyle({ WebkitLineClamp: "3" });
    expect(preview).toHaveTextContent("fourth hidden line");

    fireEvent.focus(preview);
    expect(screen.getByRole("tooltip")).toHaveTextContent(content, { normalizeWhitespace: false });
  });

  it("passes filter values to the document chunks query", () => {
    const querySpy = vi.spyOn(documentChunkQueries, "useDocumentChunksQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [], skip: 0, limit: 20, total: 0, has_more: false },
      error: null,
      refetch: vi.fn()
    } as never);

    renderPage("/document-chunks?page=3&limit=20");

    fireEvent.change(screen.getByLabelText("Document ID"), { target: { value: "11" } });
    fireEvent.change(screen.getByLabelText("Chunking profile ID"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Indexed status"), { target: { value: "true" } });

    expect(querySpy).toHaveBeenLastCalledWith({
      raw_document_id: 11,
      chunking_profile_id: 3,
      has_indexed_chunks: true,
      skip: 0,
      limit: 20
    });
  });

  it("passes URL-backed pagination to the document chunks query", () => {
    const querySpy = vi.spyOn(documentChunkQueries, "useDocumentChunksQuery").mockReturnValue({
      isLoading: false,
      isError: false,
      data: { items: [], skip: 40, limit: 20, total: 120, has_more: true },
      error: null,
      refetch: vi.fn()
    } as never);

    renderPage("/document-chunks?page=3&limit=20");

    expect(querySpy).toHaveBeenLastCalledWith({
      skip: 40,
      limit: 20
    });
  });
});

describe("getViewportBoundedTooltipPosition", () => {
  it("centers the tooltip on the trigger when it fits in the viewport", () => {
    const position = getViewportBoundedTooltipPosition(
      { left: 620, width: 80, bottom: 120, top: 80 } as DOMRect,
      { width: 1200, height: 800 },
      { width: 512, height: 288 }
    );

    expect(position).toEqual({ left: 404, top: 128, width: 512 });
  });

  it("keeps the tooltip inside the right and bottom viewport edges", () => {
    const position = getViewportBoundedTooltipPosition(
      { left: 1120, width: 80, bottom: 760, top: 720 } as DOMRect,
      { width: 1200, height: 800 },
      { width: 512, height: 288 }
    );

    expect(position).toEqual({ left: 672, top: 424, width: 512 });
  });
});
