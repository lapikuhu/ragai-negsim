import { useSearchParams } from "react-router-dom";

export type PaginatedResponse<T> = {
  items: T[];
  skip: number;
  limit: number;
  total: number;
  has_more: boolean;
};

export type PaginationParams = {
  page: number;
  limit: number;
  skip: number;
  setPage: (page: number) => void;
  setLimit: (limit: number) => void;
};

export type PaginationItem = number | "ellipsis-start" | "ellipsis-end";

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;

function parsePositiveInteger(value: string | null, fallback: number) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeLimit(value: string | null, fallback: number) {
  return Math.min(parsePositiveInteger(value, fallback), MAX_LIMIT);
}

// Backend APIs use zero-based offset pagination; the UI presents one-based page numbers.
export function paginationToSkip(page: number, limit: number) {
  const safePage = Math.max(1, Math.floor(page));
  const safeLimit = Math.max(1, Math.floor(limit));
  return (safePage - 1) * safeLimit;
}

// Convert persisted API offsets back into the one-based page number users see.
export function skipToPage(skip: number, limit: number) {
  const safeSkip = Math.max(0, Math.floor(skip));
  const safeLimit = Math.max(1, Math.floor(limit));
  return Math.floor(safeSkip / safeLimit) + 1;
}

export function clampPage(page: number, totalPages: number) {
  return Math.min(Math.max(1, Math.floor(page)), Math.max(1, Math.floor(totalPages)));
}

// Build a compact sequence: first page, current page +/- 1, last page, with ellipses for skipped ranges.
export function buildPaginationItems(currentPage: number, totalPages: number): PaginationItem[] {
  const lastPage = Math.max(1, Math.floor(totalPages));
  const current = clampPage(currentPage, lastPage);
  const pages = new Set<number>([1, lastPage]);

  for (let page = current - 1; page <= current + 1; page += 1) {
    if (page >= 1 && page <= lastPage) {
      pages.add(page);
    }
  }

  const sortedPages = Array.from(pages).sort((left, right) => left - right);
  const items: PaginationItem[] = [];
  for (const page of sortedPages) {
    const previous = items[items.length - 1];
    if (typeof previous === "number" && page - previous > 1) {
      items.push(previous === 1 ? "ellipsis-start" : "ellipsis-end");
    }
    items.push(page);
  }
  return items;
}

// List pages should use this hook so URL parsing, normalization, and skip math stay consistent.
export function usePaginationParams(defaultLimit = DEFAULT_LIMIT): PaginationParams {
  const [searchParams, setSearchParams] = useSearchParams();
  const limit = normalizeLimit(searchParams.get("limit"), defaultLimit);
  const page = parsePositiveInteger(searchParams.get("page"), 1);
  const skip = paginationToSkip(page, limit);

  const setPage = (nextPage: number) => {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(Math.max(1, Math.floor(nextPage))));
    next.set("limit", String(limit));
    setSearchParams(next);
  };

  const setLimit = (nextLimit: number) => {
    const normalized = Math.min(Math.max(1, Math.floor(nextLimit)), MAX_LIMIT);
    const next = new URLSearchParams(searchParams);
    next.set("page", "1");
    next.set("limit", String(normalized));
    setSearchParams(next);
  };

  return { page, limit, skip, setPage, setLimit };
}
