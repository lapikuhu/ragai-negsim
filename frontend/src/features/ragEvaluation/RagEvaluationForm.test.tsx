import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { makeCragConfiguration } from "./ragEvaluationTypes";
import { RagEvaluationForm } from "./RagEvaluationForm";

const catalogs = vi.hoisted(() => ({
  embeddings: [
    {
      name: "text-embedding-3-small",
      provider: "openai",
      display_name: "OpenAI text-embedding-3-small",
      dimensionality: 1536,
      normalized: false,
    },
    {
      name: "mini-l6-v2",
      provider: "huggingface",
      display_name: "Sentence Transformers all-MiniLM-L6-v2",
      dimensionality: 384,
      normalized: true,
    },
  ],
  llms: {
    providers: [
      { provider: "openai", models: [{ name: "gpt-4o-mini" }, { name: "gpt-4.1-mini" }] },
      { provider: "ollama", models: [{ name: "llama3.2" }] },
    ],
  },
}));

vi.mock("@/features/corpusIndices/corpusIndexQueries", () => ({
  useEmbeddingModelsQuery: () => ({
    data: catalogs.embeddings,
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

vi.mock("@/features/llmModels/llmModelQueries", () => ({
  useLlmModelCatalogQuery: () => ({
    data: catalogs.llms,
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

describe("RagEvaluationForm", () => {
  it("renders shared LLM defaults and all eight GraphRAG overrides", async () => {
    const user = userEvent.setup();
    render(<RagEvaluationForm submitLabel="Create experiment" onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Default LLM provider")).toBeInTheDocument();
    expect(screen.getByLabelText("Default LLM model")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("RAG strategy"), "graphrag");
    await user.click(screen.getByRole("button", { name: "Show advanced LLM overrides" }));

    expect(screen.getByLabelText("Extraction LLM model")).toBeInTheDocument();
    expect(
      screen.getByTestId("advanced-llm-overrides").querySelectorAll("select[data-llm-model]"),
    ).toHaveLength(8);
  });

  it("switches recursive, semantic, and hybrid chunking fields", async () => {
    const user = userEvent.setup();
    render(<RagEvaluationForm submitLabel="Create experiment" onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Chunk size")).toBeInTheDocument();
    expect(screen.getByLabelText("Chunk overlap")).toBeInTheDocument();
    expect(screen.getByLabelText("Separators")).toBeInTheDocument();
    expect(screen.queryByLabelText("Breakpoint threshold amount")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Chunking strategy"), "semantic");

    expect(screen.queryByLabelText("Chunk size")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Separators")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Breakpoint threshold type")).toBeInTheDocument();
    expect(screen.getByLabelText("Breakpoint threshold amount")).toBeInTheDocument();
    expect(screen.getByLabelText("Buffer size")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Chunking strategy"), "hybrid");

    expect(screen.getByLabelText("Chunk size")).toBeInTheDocument();
    expect(screen.getByLabelText("Chunk overlap")).toBeInTheDocument();
    expect(screen.getByLabelText("Separators")).toBeInTheDocument();
    expect(screen.getByLabelText("Breakpoint threshold amount")).toBeInTheDocument();
    expect(screen.getByLabelText("Buffer size")).toBeInTheDocument();
  });

  it("switches the complete CRAG and GraphRAG field sets", async () => {
    const user = userEvent.setup();
    render(<RagEvaluationForm submitLabel="Create experiment" onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Retrieval embedding model")).toBeInTheDocument();
    expect(screen.getByLabelText("Top K")).toBeInTheDocument();
    expect(screen.getByLabelText("Reranker")).toBeInTheDocument();
    expect(screen.getByLabelText("Top N")).toBeInTheDocument();
    expect(screen.getByLabelText("Rewrite limit")).toBeInTheDocument();
    expect(screen.getByLabelText("Metric K")).toBeInTheDocument();
    expect(screen.getByLabelText("Judge embedding model")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("RAG strategy"), "graphrag");

    expect(screen.queryByLabelText("Top K")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Reranker")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Graph embedding model")).toBeInTheDocument();
    expect(screen.getByLabelText("Max paths per chunk")).toBeInTheDocument();
    expect(screen.getByLabelText("Retrieval mode")).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence limit")).toBeInTheDocument();
    expect(screen.getByLabelText("Traversal depth")).toBeInTheDocument();
    expect(screen.getByLabelText("RRF constant")).toBeInTheDocument();
  });

  it("uses the validation boundaries as numeric input attributes", async () => {
    const user = userEvent.setup();
    render(<RagEvaluationForm submitLabel="Create experiment" onSubmit={vi.fn()} />);

    expect(screen.getByLabelText("Chunk size")).toHaveAttribute("min", "100");
    expect(screen.getByLabelText("Chunk size")).toHaveAttribute("max", "8000");
    expect(screen.getByLabelText("Chunk size")).toHaveAttribute("step", "1");
    expect(screen.getByLabelText("Chunk overlap")).toHaveAttribute("min", "0");
    expect(screen.getByLabelText("Chunk overlap")).toHaveAttribute("max", "2000");
    expect(screen.getByLabelText("Top K")).toHaveAttribute("max", "20");
    expect(screen.getByLabelText("Top N")).toHaveAttribute("max", "20");
    expect(screen.getByLabelText("Rewrite limit")).toHaveAttribute("max", "10");
    expect(screen.getByLabelText("Metric K")).toHaveAttribute("max", "3");

    await user.selectOptions(screen.getByLabelText("RAG strategy"), "graphrag");

    expect(screen.getByLabelText("Max paths per chunk")).toHaveAttribute("max", "100");
    expect(screen.getByLabelText("Evidence limit")).toHaveAttribute("max", "30");
    expect(screen.getByLabelText("Traversal depth")).toHaveAttribute("max", "5");
    expect(screen.getByLabelText("RRF constant")).toHaveAttribute("max", "200");
    expect(screen.getByLabelText("Metric K")).toHaveAttribute("max", "6");
  });

  it("renders the exact field error and blocks submission at an invalid boundary", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<RagEvaluationForm submitLabel="Create experiment" onSubmit={onSubmit} />);

    await user.clear(screen.getByLabelText("Top K"));
    await user.type(screen.getByLabelText("Top K"), "21");
    await user.click(screen.getByRole("button", { name: "Create experiment" }));

    expect(screen.getByText("Enter a valid value.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validates selections against the exact loaded embedding and LLM catalogs", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const initialValue = makeCragConfiguration();
    if (initialValue.rag.strategy !== "crag") {
      throw new Error("Expected a CRAG configuration");
    }
    initialValue.rag.retrieval_embedding_model = "missing-embedding";
    initialValue.rag.document_grader.model = "missing-chat-model";

    render(
      <RagEvaluationForm
        initialValue={initialValue}
        submitLabel="Save experiment"
        onSubmit={onSubmit}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Show advanced LLM overrides" }));
    await user.click(screen.getByRole("button", { name: "Save experiment" }));

    expect(screen.getByText("Select an available embedding model.")).toBeInTheDocument();
    expect(screen.getByText("Select a model available for this provider.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("synchronizes and locks Top N while the reranker is none", async () => {
    const user = userEvent.setup();
    render(<RagEvaluationForm submitLabel="Create experiment" onSubmit={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("Reranker"), "none");
    expect(screen.getByLabelText("Top N")).toBeDisabled();
    expect(screen.getByLabelText("Top N")).toHaveValue(4);

    await user.clear(screen.getByLabelText("Top K"));
    await user.type(screen.getByLabelText("Top K"), "7");
    expect(screen.getByLabelText("Top N")).toHaveValue(7);
  });

  it("applies a shared default to every GraphRAG LLM role", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<RagEvaluationForm submitLabel="Create experiment" onSubmit={onSubmit} />);

    await user.selectOptions(screen.getByLabelText("RAG strategy"), "graphrag");
    await user.click(screen.getByRole("button", { name: "Show advanced LLM overrides" }));
    await user.selectOptions(screen.getByLabelText("Default LLM provider"), "ollama");

    const overrideModels = within(screen.getByTestId("advanced-llm-overrides")).getAllByRole(
      "combobox",
      { name: /LLM model$/ },
    );
    expect(overrideModels).toHaveLength(8);
    for (const model of overrideModels) {
      expect(model).toHaveValue("llama3.2");
    }

    await user.click(screen.getByRole("button", { name: "Create experiment" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submitted = onSubmit.mock.calls[0][0];
    expect(submitted.rag).toMatchObject({
      extraction_llm: { provider: "ollama", model: "llama3.2" },
      document_grader: { provider: "ollama", model: "llama3.2" },
      query_rewriter: { provider: "ollama", model: "llama3.2" },
      answer_generator: { provider: "ollama", model: "llama3.2" },
      hallucination_grader: { provider: "ollama", model: "llama3.2" },
      answer_grader: { provider: "ollama", model: "llama3.2" },
      fallback_generator: { provider: "ollama", model: "llama3.2" },
    });
    expect(submitted.metrics.ragas_judge).toEqual({ provider: "ollama", model: "llama3.2" });
  });

  it("normalizes edit submissions and preserves the final empty separator", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const initialValue = makeCragConfiguration();
    initialValue.name = "  Edited experiment  ";

    render(
      <RagEvaluationForm
        initialValue={initialValue}
        submitLabel="Save experiment"
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByLabelText("Separators")).toHaveValue("\\n\\n\n\\n\n \n");
    await user.click(screen.getByRole("button", { name: "Save experiment" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toEqual({
      ...initialValue,
      name: "Edited experiment",
      chunking: {
        strategy: "recursive",
        chunk_size: 1000,
        chunk_overlap: 200,
        separators: ["\n\n", "\n", " ", ""],
      },
    });
    expect(onSubmit.mock.calls[0][0]).toHaveProperty("rag");
    expect(onSubmit.mock.calls[0][0]).toHaveProperty("metrics");
  });

  it("calls the optional cancel action without submitting", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const onCancel = vi.fn();
    render(
      <RagEvaluationForm
        submitLabel="Create experiment"
        onSubmit={onSubmit}
        onCancel={onCancel}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a second same-tick submit before the async submission settles", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn(() => new Promise<void>(() => undefined));
    const { container } = render(
      <RagEvaluationForm submitLabel="Create experiment" onSubmit={onSubmit} />,
    );
    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Single submission");
    const form = container.querySelector("form");
    if (!form) {
      throw new Error("Expected the RAG evaluation form");
    }

    act(() => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
