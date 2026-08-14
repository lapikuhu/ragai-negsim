import { describe, expect, it } from "vitest";

import type { SimulationRetrievalOptionsResponse } from "@/api/types";
import { simulationKeys } from "./simulationQueries";
import {
  filterRetrievalOptions,
  reconcileRetrievalSelection,
} from "./simulationRetrievalOptions";


const options: SimulationRetrievalOptionsResponse = {
  mode: "hybrid",
  dense_indices: [
    { id: 101, name: "Dense A" },
    { id: 102, name: "Dense B" },
  ],
  bm25_indices: [
    { id: 201, name: "BM25 A" },
    { id: 202, name: "BM25 B" },
  ],
  compatible_pairs: [
    { corpus_index_id: 101, bm25_index_id: 201 },
    { corpus_index_id: 102, bm25_index_id: 202 },
  ],
};


describe("simulation retrieval options", () => {
  it("keys retrieval options by both authoritative inputs", () => {
    expect(simulationKeys.retrievalOptions(44, 7)).toEqual([
      "simulations",
      "retrieval-options",
      44,
      7,
    ]);
  });

  it("shows every pairable artifact before either side is selected", () => {
    const filtered = filterRetrievalOptions(options, "", "");

    expect(filtered.dense.map((item) => item.id)).toEqual([101, 102]);
    expect(filtered.bm25.map((item) => item.id)).toEqual([201, 202]);
  });

  it("filters either side from the selected counterpart", () => {
    expect(
      filterRetrievalOptions(options, "", "201").dense.map((item) => item.id),
    ).toEqual([101]);
    expect(
      filterRetrievalOptions(options, "102", "").bm25.map((item) => item.id),
    ).toEqual([202]);
  });

  it("preserves an opposite selection that remains compatible", () => {
    expect(
      reconcileRetrievalSelection(
        options,
        { corpusIndexId: "101", bm25IndexId: "201" },
        "dense",
      ),
    ).toEqual({ corpusIndexId: "101", bm25IndexId: "201" });
  });

  it("clears only the opposite selection after an incompatible dense change", () => {
    expect(
      reconcileRetrievalSelection(
        options,
        { corpusIndexId: "102", bm25IndexId: "201" },
        "dense",
      ),
    ).toEqual({ corpusIndexId: "102", bm25IndexId: "" });
  });

  it("clears only the opposite selection after an incompatible BM25 change", () => {
    expect(
      reconcileRetrievalSelection(
        options,
        { corpusIndexId: "101", bm25IndexId: "202" },
        "bm25",
      ),
    ).toEqual({ corpusIndexId: "", bm25IndexId: "202" });
  });

  it("clears selections removed by a refreshed response", () => {
    const refreshed = {
      ...options,
      dense_indices: [{ id: 102, name: "Dense B" }],
      bm25_indices: [{ id: 202, name: "BM25 B" }],
      compatible_pairs: [{ corpus_index_id: 102, bm25_index_id: 202 }],
    };

    expect(
      reconcileRetrievalSelection(
        refreshed,
        { corpusIndexId: "101", bm25IndexId: "201" },
        "refresh",
      ),
    ).toEqual({ corpusIndexId: "", bm25IndexId: "" });
  });

  it("clears both refreshed selections when their pair disappeared", () => {
    const refreshed = {
      ...options,
      compatible_pairs: [
        { corpus_index_id: 101, bm25_index_id: 202 },
        { corpus_index_id: 102, bm25_index_id: 201 },
      ],
    };

    expect(
      reconcileRetrievalSelection(
        refreshed,
        { corpusIndexId: "101", bm25IndexId: "201" },
        "refresh",
      ),
    ).toEqual({ corpusIndexId: "", bm25IndexId: "" });
  });
});
