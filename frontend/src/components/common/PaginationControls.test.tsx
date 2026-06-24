import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PaginationControls } from "./PaginationControls";

describe("PaginationControls", () => {
  it("renders compact page navigation and emits selected pages", () => {
    const onPageChange = vi.fn();

    render(<PaginationControls page={5} limit={20} total={200} onPageChange={onPageChange} />);

    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
    expect(screen.getAllByText("...").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Go to page 6" }));

    expect(onPageChange).toHaveBeenCalledWith(6);
  });

  it("disables boundary arrows", () => {
    render(<PaginationControls page={1} limit={20} total={40} onPageChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
  });

  it("centers the navigation within its list container", () => {
    render(<PaginationControls page={2} limit={20} total={80} onPageChange={vi.fn()} />);

    expect(screen.getByLabelText("Pagination")).toHaveClass("justify-center");
    expect(screen.getByLabelText("Pagination")).not.toHaveClass("justify-end");
  });
});
