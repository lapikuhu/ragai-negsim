import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VectorStoreForm } from "./VectorStoreForm";

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useEmbeddingModelsQuery: () => ({
    isLoading: false,
    data: [
      {
        name: "mini-l6-v2",
        display_name: "MiniLM L6",
        dimensionality: 384
      }
    ]
  })
}));

describe("VectorStoreForm", () => {
  it("keeps the Name field aligned with the Embedding model dropdown", () => {
    render(
      <VectorStoreForm
        submitLabel="Create vector store"
        submittingLabel="Creating..."
        successMessage="Vector store created."
        onSubmit={vi.fn().mockResolvedValue({})}
      />
    );

    const nameField = screen.getByLabelText("Name").closest("label");
    const embeddingModelField = screen.getByLabelText(/Embedding model/).closest("label");

    expect(nameField).not.toBeNull();
    expect(embeddingModelField).not.toBeNull();
    expect(nameField).toHaveClass("content-start");
    expect(embeddingModelField).toHaveClass("content-start");
  });
});
