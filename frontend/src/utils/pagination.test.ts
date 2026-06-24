import { describe, expect, it } from "vitest";

import {
  buildPaginationItems,
  clampPage,
  paginationToSkip,
  skipToPage
} from "./pagination";

describe("pagination utilities", () => {
  it("converts one-based pages to backend offsets", () => {
    expect(paginationToSkip(1, 20)).toBe(0);
    expect(paginationToSkip(3, 20)).toBe(40);
  });

  it("converts backend offsets to one-based pages", () => {
    expect(skipToPage(0, 20)).toBe(1);
    expect(skipToPage(40, 20)).toBe(3);
  });

  it("clamps pages within the available range", () => {
    expect(clampPage(-4, 5)).toBe(1);
    expect(clampPage(9, 5)).toBe(5);
  });

  it("builds compact page items with ellipses", () => {
    expect(buildPaginationItems(5, 10)).toEqual([1, "ellipsis-start", 4, 5, 6, "ellipsis-end", 10]);
  });
});
