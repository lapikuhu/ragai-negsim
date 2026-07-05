import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsPage } from "./DocumentsPage";

const state = vi.hoisted(() => ({
  documentsQuery: {
    isLoading: false,
    isError: false,
    data: [
      {
        id: 7,
        name: "Negotiation brief",
        description: "Detail test document",
        document_title: "Getting to Yes",
        document_author: "Roger Fisher",
        document_date: "05-07-2026",
        source_path: "app/raw_docs_store/brief.pdf",
        source_hash: "abc123",
        source_size: 2048,
        source_mtime: "2026-06-24T10:00:00Z",
        source_status: "available",
        uploaded_at: "2026-06-24T10:05:00Z",
        uploaded_by_user_id: 12,
        uploaded_by_username: "teacher" as string | null,
        associated_corpora: [],
        parsed_at: null
      }
    ],
    error: null as Error | null,
    refetch: vi.fn()
  },
  corporaQuery: {
    data: [{ id: 4, name: "Negotiation corpus", description: "Practice briefs" }]
  },
  uploadMutation: {
    isPending: false,
    mutateAsync: vi.fn()
  }
}));

vi.mock("@/features/documents/documentQueries", () => ({
  useDocumentsQuery: () => state.documentsQuery,
  useUploadDocumentMutation: () => state.uploadMutation
}));

vi.mock("@/features/corpora/corpusQueries", () => ({
  useCorporaQuery: () => state.corporaQuery
}));

describe("DocumentsPage", () => {
  beforeEach(() => {
    state.uploadMutation.isPending = false;
    state.uploadMutation.mutateAsync = vi.fn().mockResolvedValue(state.documentsQuery.data[0]);
  });

  it("shows raw document bibliographic metadata under the document name", () => {
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    const documentLink = screen.getByRole("link", { name: "Negotiation brief" });
    const documentCell = documentLink.closest("td");

    expect(documentCell).not.toBeNull();
    expect(within(documentCell as HTMLElement).getByText("Getting to Yes")).toBeInTheDocument();
    expect(within(documentCell as HTMLElement).getByText("Roger Fisher")).toBeInTheDocument();
    expect(within(documentCell as HTMLElement).getByText("05-07-2026")).toBeInTheDocument();
  });

  it("submits title, author, and date metadata when uploading a document", async () => {
    const user = userEvent.setup();
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    await user.type(screen.getByLabelText("Name"), "Labor casebook");
    await user.type(screen.getByLabelText("Title"), "Labor Negotiation Playbook");
    await user.type(screen.getByLabelText("Author"), "Ada Lovelace");
    await user.type(screen.getByLabelText("Date"), "2026-07-05");
    await user.type(screen.getByPlaceholderText("e.g. 1,2"), "4");
    await user.upload(
      screen.getByLabelText("PDF file"),
      new File(["brief"], "brief.pdf", { type: "application/pdf" })
    );
    await user.click(screen.getByRole("button", { name: "Upload document" }));

    expect(state.uploadMutation.mutateAsync).toHaveBeenCalledWith({
      name: "Labor casebook",
      description: "",
      documentTitle: "Labor Negotiation Playbook",
      documentAuthor: "Ada Lovelace",
      documentDate: "05-07-2026",
      corpusIds: [4],
      file: expect.any(File)
    });
  });
});
