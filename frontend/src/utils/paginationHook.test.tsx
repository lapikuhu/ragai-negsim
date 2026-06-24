import { MemoryRouter, useLocation } from "react-router-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { usePaginationParams } from "./pagination";

function Probe() {
  const location = useLocation();
  const pagination = usePaginationParams();
  return (
    <div>
      <span>page:{pagination.page}</span>
      <span>limit:{pagination.limit}</span>
      <span>skip:{pagination.skip}</span>
      <span>search:{location.search}</span>
      <button type="button" onClick={() => pagination.setPage(4)}>
        Page 4
      </button>
      <button type="button" onClick={() => pagination.setLimit(50)}>
        Limit 50
      </button>
    </div>
  );
}

function renderProbe(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Probe />
    </MemoryRouter>
  );
}

describe("usePaginationParams", () => {
  it("normalizes invalid URL pagination values", () => {
    renderProbe("/document-chunks?page=-2&limit=999");

    expect(screen.getByText("page:1")).toBeInTheDocument();
    expect(screen.getByText("limit:100")).toBeInTheDocument();
    expect(screen.getByText("skip:0")).toBeInTheDocument();
  });

  it("preserves unrelated filters when page changes", () => {
    renderProbe("/document-chunks?raw_document_id=11&page=2&limit=20");

    fireEvent.click(screen.getByRole("button", { name: "Page 4" }));

    expect(screen.getByText("search:?raw_document_id=11&page=4&limit=20")).toBeInTheDocument();
  });

  it("resets to page one when limit changes", () => {
    renderProbe("/document-chunks?raw_document_id=11&page=4&limit=20");

    fireEvent.click(screen.getByRole("button", { name: "Limit 50" }));

    expect(screen.getByText("search:?raw_document_id=11&page=1&limit=50")).toBeInTheDocument();
  });
});
