import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
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
      associated_corpora: [{ id: 4, name: "Negotiation corpus", description: "Practice briefs" }],
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
  },
  updateMutation: {
    isPending: false,
    mutateAsync: vi.fn()
  },
  auth: {
    user: {
      id: 12,
      roles: [{ id: 2, name: "teacher" }]
    },
    hasRole: vi.fn((...roles: string[]) => roles.includes("teacher"))
  }
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ documentId: "7" })
  };
});

vi.mock("@/features/documents/documentQueries", () => ({
  useDocumentDetailQuery: () => state.query,
  useIngestDocumentMutation: () => state.ingestMutation,
  useChunkDocumentMutation: () => state.chunkMutation,
  useUpdateDocumentMutation: () => state.updateMutation
}));

vi.mock("@/app/AuthProvider", () => ({
  useAuth: () => state.auth
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
      associated_corpora: [{ id: 4, name: "Negotiation corpus", description: "Practice briefs" }],
      parsed_at: null
    };
    state.updateMutation.isPending = false;
    state.updateMutation.mutateAsync.mockReset();
    state.updateMutation.mutateAsync.mockResolvedValue(state.query.data);
    state.auth.user = {
      id: 12,
      roles: [{ id: 2, name: "teacher" }]
    };
    state.auth.hasRole.mockImplementation((...roles: string[]) => roles.includes("teacher"));
  });

  it("shows the uploader username when the API provides it", () => {
    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    expect(screen.getByText("teacher")).toBeInTheDocument();
    expect(screen.queryByText(/^12$/)).not.toBeInTheDocument();
  });

  it("shows bibliographic metadata", () => {
    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    expect(screen.getByText("Document title")).toBeInTheDocument();
    expect(screen.getByText("Getting to Yes")).toBeInTheDocument();
    expect(screen.getByText("Author")).toBeInTheDocument();
    expect(screen.getByText("Roger Fisher")).toBeInTheDocument();
    expect(screen.getByText("Document year")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
  });

  it("falls back to the uploader id when username is missing", () => {
    state.query.data = {
      ...state.query.data,
      uploaded_by_username: null
    };

    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("shows associated corpora as links and hides the parsed timestamp", () => {
    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    const corpusLink = screen.getByRole("link", { name: /Negotiation corpus/i });

    expect(corpusLink).toHaveAttribute("href", "/corpora/4");
    expect(screen.getByText("ID 4")).toBeInTheDocument();
    expect(screen.queryByText("Parsed at")).not.toBeInTheDocument();
  });

  it("shows a neutral empty state when the document is not associated with any corpora", () => {
    state.query.data = {
      ...state.query.data,
      associated_corpora: []
    };

    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    expect(screen.getByText("No associated corpora")).toBeInTheDocument();
  });

  it("shows edit controls for the uploading teacher", () => {
    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    expect(screen.getByRole("button", { name: /edit metadata/i })).toBeInTheDocument();
  });

  it("shows edit controls for admins even when they did not upload the document", () => {
    state.auth.user = {
      id: 99,
      roles: [{ id: 1, name: "admin" }]
    };
    state.auth.hasRole.mockImplementation((...roles: string[]) => roles.includes("admin"));

    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    expect(screen.getByRole("button", { name: /edit metadata/i })).toBeInTheDocument();
  });

  it("hides edit controls from non-owner teachers and students", () => {
    state.auth.user = {
      id: 99,
      roles: [{ id: 2, name: "teacher" }]
    };

    const { rerender } = render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    expect(screen.queryByRole("button", { name: /edit metadata/i })).not.toBeInTheDocument();

    state.auth.user = {
      id: 99,
      roles: [{ id: 3, name: "student" }]
    };
    state.auth.hasRole.mockImplementation((...roles: string[]) => roles.includes("student"));

    rerender(<DocumentDetailPage />);

    expect(screen.queryByRole("button", { name: /edit metadata/i })).not.toBeInTheDocument();
  });

  it("submits metadata-only PATCH payloads from the edit form", async () => {
    const user = userEvent.setup();

    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
    await user.clear(screen.getByLabelText("Name-Alias"));
    await user.type(screen.getByLabelText("Name-Alias"), "Updated brief");
    await user.clear(screen.getByLabelText("Title"));
    await user.type(screen.getByLabelText("Title"), "Updated title");
    await user.clear(screen.getByLabelText("Author"));
    await user.type(screen.getByLabelText("Author"), "Updated author");
    await user.clear(screen.getByLabelText("Year"));
    await user.type(screen.getByLabelText("Year"), "2027");
    await user.clear(screen.getByLabelText("Description"));
    await user.type(screen.getByLabelText("Description"), "Updated description");
    await user.click(screen.getByRole("button", { name: /save metadata/i }));

    expect(state.updateMutation.mutateAsync).toHaveBeenCalledWith({
      name: "Updated brief",
      description: "Updated description",
      document_title: "Updated title",
      document_author: "Updated author",
      document_year: 2027
    });
    expect(state.updateMutation.mutateAsync).not.toHaveBeenCalledWith(
      expect.objectContaining({
        source_path: expect.anything()
      })
    );
    expect(await screen.findByText("Metadata updated.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save metadata/i })).not.toBeInTheDocument();
  });

  it("shows validation for non-integer document years before PATCH", async () => {
    const user = userEvent.setup();

    render(<DocumentDetailPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole("button", { name: /edit metadata/i }));
    await user.clear(screen.getByLabelText("Year"));
    await user.type(screen.getByLabelText("Year"), "2026.5");
    await user.click(screen.getByRole("button", { name: /save metadata/i }));

    expect(screen.getByText("Year must be an integer.")).toBeInTheDocument();
    expect(state.updateMutation.mutateAsync).not.toHaveBeenCalled();
  });
});
