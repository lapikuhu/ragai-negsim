import { render, screen } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { router } from "./router";

describe("router", () => {
  it("renders the public not-found page for the removed settings URL", async () => {
    await router.navigate("/settings");

    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
  });
});
