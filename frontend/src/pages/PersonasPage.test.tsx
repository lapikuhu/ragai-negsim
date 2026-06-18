import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as personaQueries from "@/features/counterpartPersonas/personaQueries";

import { PersonasPage } from "./PersonasPage";

function renderPage(personas: unknown[]) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  vi.spyOn(personaQueries, "usePersonasQuery").mockReturnValue({
    isLoading: false,
    isError: false,
    data: personas,
    refetch: vi.fn()
  } as never);
  vi.spyOn(personaQueries, "useCreatePersonaMutation").mockReturnValue({
    isPending: false,
    mutateAsync: vi.fn()
  } as never);
  vi.spyOn(personaQueries, "useUpdatePersonaMutation").mockReturnValue({
    isPending: false,
    mutateAsync: vi.fn()
  } as never);

  return render(
    <QueryClientProvider client={client}>
      <PersonasPage />
    </QueryClientProvider>
  );
}

describe("PersonasPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders persona descriptions as markdown", () => {
    renderPage([
      {
        id: 1,
        name: "Firm buyer",
        description: "Negotiates with **firm anchors**.\n\n- Keeps calm\n- Uses `BATNA`",
        created_at: "2026-06-18T00:00:00Z",
        last_updated: "2026-06-18T00:00:00Z"
      }
    ]);

    expect(screen.getByText("firm anchors").tagName).toBe("STRONG");
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByText("Keeps calm").tagName).toBe("LI");
    expect(screen.getByText("BATNA").tagName).toBe("CODE");
  });

  it("does not inject raw HTML from persona markdown", () => {
    const { container } = renderPage([
      {
        id: 2,
        name: "HTML attempt",
        description: '<script>alert("x")</script>\n\n<strong>Injected</strong>',
        created_at: "2026-06-18T00:00:00Z",
        last_updated: "2026-06-18T00:00:00Z"
      }
    ]);

    expect(container.querySelector("script")).not.toBeInTheDocument();
    expect(container.querySelector("strong")).not.toBeInTheDocument();
    expect(screen.getByText(/<strong>Injected<\/strong>/)).toBeInTheDocument();
  });

  it("shows a seven-line collapsed preview and expands long markdown descriptions", async () => {
    const user = userEvent.setup();
    renderPage([
      {
        id: 3,
        name: "Detailed negotiator",
        description: [
          "# Operating style",
          "line 2",
          "line 3",
          "line 4",
          "line 5",
          "line 6",
          "line 7",
          "line 8",
          "line 9"
        ].join("\n"),
        created_at: "2026-06-18T00:00:00Z",
        last_updated: "2026-06-18T00:00:00Z"
      }
    ]);

    const preview = screen.getByTestId("persona-description-preview");

    expect(preview).toHaveClass("max-h-[10.5rem]");
    expect(preview).toHaveClass("overflow-hidden");
    expect(screen.getByText("...")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show more" }));

    expect(preview).not.toHaveClass("max-h-[10.5rem]");
    expect(preview).not.toHaveClass("overflow-hidden");
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument();
  });
});