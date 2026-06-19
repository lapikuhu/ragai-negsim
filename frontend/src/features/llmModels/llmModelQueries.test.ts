import { describe, expect, it } from "vitest";

import { llmModelCatalogQueryOptions, llmModelKeys } from "./llmModelQueries";

describe("llmModelCatalogQueryOptions", () => {
  it("uses the shared query key and cache settings", () => {
    const options = llmModelCatalogQueryOptions();

    expect(options.queryKey).toEqual(llmModelKeys.catalog);
    expect(options.staleTime).toBe(60 * 60 * 1000);
    expect(options.gcTime).toBe(120 * 60 * 1000);
    expect(options.queryFn).toBeTypeOf("function");
  });
});
