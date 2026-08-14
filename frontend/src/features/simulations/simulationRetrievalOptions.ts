import type {
  SimulationRetrievalIndexOption,
  SimulationRetrievalOptionsResponse,
} from "@/api/types";


export type RetrievalSelection = {
  corpusIndexId: string;
  bm25IndexId: string;
};

type ChangedSelection = "dense" | "bm25" | "refresh";

export function arePaired(
  response: SimulationRetrievalOptionsResponse,
  corpusIndexId: string,
  bm25IndexId: string,
) {
  return (response.compatible_pairs ?? []).some(
    (pair) => String(pair.corpus_index_id) === corpusIndexId
      && String(pair.bm25_index_id) === bm25IndexId,
  );
}

export function filterRetrievalOptions(
  response: SimulationRetrievalOptionsResponse,
  corpusIndexId: string,
  bm25IndexId: string,
): {
  dense: SimulationRetrievalIndexOption[];
  bm25: SimulationRetrievalIndexOption[];
} {
  const dense = response.dense_indices ?? [];
  const bm25 = response.bm25_indices ?? [];
  const pairs = response.compatible_pairs ?? [];

  return {
    dense: bm25IndexId
      ? dense.filter((index) => pairs.some(
          (pair) => pair.corpus_index_id === index.id
            && String(pair.bm25_index_id) === bm25IndexId,
        ))
      : dense,
    bm25: corpusIndexId
      ? bm25.filter((index) => pairs.some(
          (pair) => pair.bm25_index_id === index.id
            && String(pair.corpus_index_id) === corpusIndexId,
        ))
      : bm25,
  };
}

export function reconcileRetrievalSelection(
  response: SimulationRetrievalOptionsResponse,
  selection: RetrievalSelection,
  changed: ChangedSelection,
): RetrievalSelection {
  let corpusIndexId = selection.corpusIndexId;
  let bm25IndexId = selection.bm25IndexId;

  if (changed === "refresh") {
    const denseIds = new Set((response.dense_indices ?? []).map((item) => String(item.id)));
    const bm25Ids = new Set((response.bm25_indices ?? []).map((item) => String(item.id)));
    if (corpusIndexId && !denseIds.has(corpusIndexId)) corpusIndexId = "";
    if (bm25IndexId && !bm25Ids.has(bm25IndexId)) bm25IndexId = "";
    if (
      response.mode === "hybrid"
      && corpusIndexId
      && bm25IndexId
      && !arePaired(response, corpusIndexId, bm25IndexId)
    ) {
      corpusIndexId = "";
      bm25IndexId = "";
    }
  } else if (
    changed === "dense"
    && corpusIndexId
    && bm25IndexId
    && !arePaired(response, corpusIndexId, bm25IndexId)
  ) {
    bm25IndexId = "";
  } else if (
    changed === "bm25"
    && corpusIndexId
    && bm25IndexId
    && !arePaired(response, corpusIndexId, bm25IndexId)
  ) {
    corpusIndexId = "";
  }

  return { corpusIndexId, bm25IndexId };
}
