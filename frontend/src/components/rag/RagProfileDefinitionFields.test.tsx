import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RagProfileDefinitionRead } from "@/api/types";
import {
  RagProfileDefinitionFields,
  buildFieldValues,
  getCragEffectiveCapacity,
  getCragRetrievalMode,
  packDefinitionFieldValues,
  updateDefinitionFieldValues,
  validateCragFieldValues,
} from "./RagProfileDefinitionFields";

const definition: RagProfileDefinitionRead = {
  strategy: "crag",
  label: "Corrective RAG",
  fields: [
    { name: "bm25_weight", kind: "float", label: "BM25 weight", required: true, default: 0, minimum: 0, maximum: 1, help_text: "Choose retrieval mode.", options: [] },
    { name: "dense_k", kind: "int", label: "Dense candidates", required: true, default: 4, minimum: 1, maximum: 20, options: [] },
    { name: "bm25_k", kind: "int", label: "BM25 candidates", required: true, default: 4, minimum: 1, maximum: 20, options: [] },
    { name: "final_top_k", kind: "int", label: "Final retrieval results", required: true, default: 4, minimum: 1, maximum: 20, options: [] },
    { name: "reranker", kind: "enum", label: "Reranker", required: true, default: "cross_encoder", options: ["cross_encoder", "none"] },
    { name: "top_n", kind: "int", label: "Reranked documents", required: true, default: 3, minimum: 1, maximum: 20, options: [] },
    { name: "max_rewrite_attempts", kind: "int", label: "Rewrite attempts", required: true, default: 2, minimum: 0, maximum: 10, options: [] },
  ],
};

function Harness() {
  const [values, setValues] = useState(() => buildFieldValues(definition));
  return (
    <RagProfileDefinitionFields
      definition={definition}
      fieldValues={values}
      onChange={(fieldName, value) => {
        setValues((current) => updateDefinitionFieldValues(definition, current, fieldName, value));
      }}
    />
  );
}

describe("RagProfileDefinitionFields", () => {
  it("renders definition metadata and disables candidates outside the active mode", () => {
    render(<Harness />);

    expect(screen.getByText("Dense retrieval")).toBeInTheDocument();
    expect(screen.getByText("Choose retrieval mode.")).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Dense candidates" })).toBeEnabled();
    expect(screen.getByRole("spinbutton", { name: "BM25 candidates" })).toBeDisabled();
    expect(screen.getByRole("spinbutton", { name: /^BM25 weight/ })).toHaveAttribute("step", "0.1");

    fireEvent.change(screen.getByRole("spinbutton", { name: /^BM25 weight/ }), {
      target: { value: "1" },
    });

    expect(screen.getByText("BM25 retrieval")).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Dense candidates" })).toBeDisabled();
    expect(screen.getByRole("spinbutton", { name: "BM25 candidates" })).toBeEnabled();
  });

  it("coerces integer and float fields and derives mode-specific capacity", () => {
    const values = buildFieldValues(definition, {
      bm25_weight: 0.4,
      dense_k: 8,
      bm25_k: 6,
      final_top_k: 5,
      top_n: 3,
    });

    expect(packDefinitionFieldValues(definition, values)).toEqual({
      bm25_weight: 0.4,
      dense_k: 8,
      bm25_k: 6,
      final_top_k: 5,
      reranker: "cross_encoder",
      top_n: 3,
      max_rewrite_attempts: 2,
    });
    expect(getCragRetrievalMode(values)).toBe("hybrid");
    expect(getCragEffectiveCapacity(values)).toBe(5);
    expect(getCragEffectiveCapacity({ ...values, bm25_weight: "0", final_top_k: "9" })).toBe(8);
    expect(getCragEffectiveCapacity({ ...values, bm25_weight: "1", final_top_k: "9" })).toBe(6);
  });

  it("synchronizes and disables top n when reranking is disabled", () => {
    const initial = buildFieldValues(definition, {
      bm25_weight: 0,
      dense_k: 7,
      final_top_k: 5,
      top_n: 3,
    });
    const values = updateDefinitionFieldValues(definition, initial, "reranker", "none");

    expect(values.top_n).toBe("5");

    render(
      <RagProfileDefinitionFields
        definition={definition}
        fieldValues={values}
        onChange={() => undefined}
      />,
    );
    expect(screen.getByRole("spinbutton", { name: "Reranked documents" })).toBeDisabled();
  });

  it("reports final and reranked limits against effective capacity", () => {
    const values = buildFieldValues(definition, {
      bm25_weight: 0,
      dense_k: 4,
      bm25_k: 8,
      final_top_k: 9,
      top_n: 5,
    });

    expect(validateCragFieldValues(values)).toEqual({
      final_top_k: "Final retrieval results cannot exceed the larger candidate limit.",
      top_n: "Reranked documents cannot exceed the effective retrieval capacity.",
    });
  });

  it("renders field-level validation errors supplied by a consuming form", () => {
    render(
      <RagProfileDefinitionFields
        definition={definition}
        fieldValues={buildFieldValues(definition)}
        errors={{ final_top_k: "Final limit is invalid." }}
        onChange={() => undefined}
      />,
    );

    expect(screen.getByText("Final limit is invalid.")).toBeInTheDocument();
  });
});
