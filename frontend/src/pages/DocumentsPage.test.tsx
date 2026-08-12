import { createRef } from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsPage } from "./DocumentsPage";
import { Input } from "@/components/ui/Field";

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
        document_year: 2026,
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
    expect(within(documentCell as HTMLElement).getByText("2026")).toBeInTheDocument();
  });

  it("submits title, author, and year metadata when uploading a document", async () => {
    const user = userEvent.setup();
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    await user.type(screen.getByLabelText(/Name-Alias/), "Labor casebook");
    await user.type(screen.getByLabelText("Title"), "Labor Negotiation Playbook");
    await user.type(screen.getByLabelText("Author"), "Ada Lovelace");
    await user.type(screen.getByLabelText("Year"), "2026");
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
      documentYear: 2026,
      corpusIds: [4],
      file: expect.any(File)
    });
  });

  it("forwards an input ref to the HTML input element", () => {
    const ref = createRef<HTMLInputElement>();
    render(<Input ref={ref} />);

    expect(ref.current).toBe(screen.getByRole("textbox"));
  });

  it("keeps the selected PDF while an upload is pending and clears it after success", async () => {
    const user = userEvent.setup();
    let resolveUpload: (() => void) | undefined;
    state.uploadMutation.mutateAsync = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveUpload = resolve;
        })
    );
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    const fileInput = screen.getByLabelText("PDF file") as HTMLInputElement;
    await user.type(screen.getByLabelText(/Name-Alias/), "Labor casebook");
    await user.upload(fileInput, new File(["brief"], "brief.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Upload document" }));

    expect(state.uploadMutation.mutateAsync).toHaveBeenCalledOnce();
    expect(fileInput.files?.[0]?.name).toBe("brief.pdf");

    resolveUpload?.();
    await waitFor(() => expect(fileInput).toHaveValue(""));
  });

  it("clears the selected PDF when the clear control is pressed", async () => {
    const user = userEvent.setup();
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    const fileInput = screen.getByLabelText("PDF file") as HTMLInputElement;
    await user.type(screen.getByLabelText(/Name-Alias/), "Labor casebook");
    await user.upload(fileInput, new File(["brief"], "brief.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Clear selected file" }));

    expect(fileInput).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    expect(screen.getByText("Choose a file first.")).toBeInTheDocument();
  });

  it("clears the upload success message when another PDF is selected", async () => {
    const user = userEvent.setup();
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    await user.type(screen.getByLabelText(/Name-Alias/), "Labor casebook");
    const fileInput = screen.getByLabelText("PDF file");
    await user.upload(fileInput, new File(["brief"], "brief.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Upload document" }));
    await screen.findByText("Upload complete.");

    await user.upload(fileInput, new File(["replacement"], "replacement.pdf", { type: "application/pdf" }));

    expect(screen.queryByText("Upload complete.")).not.toBeInTheDocument();
  });

  it("keeps the Title upload field aligned with the Name-Alias field", () => {
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    const nameField = screen.getByLabelText(/Name-Alias/).closest("label");
    const titleField = screen.getByLabelText("Title").closest("label");

    expect(nameField).not.toBeNull();
    expect(titleField).not.toBeNull();
    expect(nameField).toHaveClass("content-start", "min-h-[82px]");
    expect(titleField).toHaveClass("content-start", "min-h-[82px]");
  });

  it("keeps the Linked corpus IDs upload field aligned with the Description field", () => {
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    const corpusIdsField = screen.getByLabelText(/Linked corpus IDs/).closest("label");
    const descriptionField = screen.getByLabelText("Description").closest("label");

    expect(corpusIdsField).not.toBeNull();
    expect(descriptionField).not.toBeNull();
    expect(corpusIdsField).toHaveClass("content-start");
    expect(descriptionField).toHaveClass("content-start");
  });

  it("retains the selected PDF when year validation fails", async () => {
    const user = userEvent.setup();
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    await user.type(screen.getByLabelText(/Name-Alias/), "Labor casebook");
    await user.type(screen.getByLabelText("Year"), "2026.5");
    await user.upload(
      screen.getByLabelText("PDF file"),
      new File(["brief"], "brief.pdf", { type: "application/pdf" })
    );
    await user.click(screen.getByRole("button", { name: "Upload document" }));

    expect(state.uploadMutation.mutateAsync).not.toHaveBeenCalled();
    expect(screen.getByText("Year must be an integer.")).toBeInTheDocument();
    expect((screen.getByLabelText("PDF file") as HTMLInputElement).files?.[0]?.name).toBe("brief.pdf");
  });

  it("retains the selected PDF when the upload is rejected", async () => {
    const user = userEvent.setup();
    state.uploadMutation.mutateAsync = vi.fn().mockRejectedValue(new Error("Upload failed."));
    render(<DocumentsPage />, { wrapper: MemoryRouter });

    const fileInput = screen.getByLabelText("PDF file") as HTMLInputElement;
    await user.type(screen.getByLabelText(/Name-Alias/), "Labor casebook");
    await user.upload(fileInput, new File(["brief"], "brief.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Upload document" }));

    await waitFor(() => expect(screen.getByText("Upload failed.")).toBeInTheDocument());
    expect(fileInput.files?.[0]?.name).toBe("brief.pdf");
  });
});
