import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";

vi.mock("@/components/layout/Sidebar", () => ({
  Sidebar: () => <aside>Sidebar</aside>
}));

vi.mock("@/components/layout/Topbar", () => ({
  Topbar: () => <header data-testid="topbar">Topbar</header>
}));

vi.mock("react-router-dom", () => ({
  Outlet: () => <div>Page content</div>
}));

describe("AppShell", () => {
  it("packs the workspace rows at the top instead of stretching them to the sidebar height", () => {
    render(<AppShell />);

    expect(screen.getByTestId("topbar").parentElement).toHaveClass("content-start");
  });
});
