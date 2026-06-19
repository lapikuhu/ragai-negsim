import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { LLMModelCatalogResponse, LLMSelection } from "@/api/types";
import { LlmModelSelector, getDefaultCatalogModel } from "./LlmModelSelector";

const catalog: LLMModelCatalogResponse = {
  providers: [
    { provider: "openai", models: [{ name: "gpt-4o-mini" }, { name: "gpt-4.1-mini" }] },
    {
      provider: "ollama",
      models: [{ name: "qwen2.5:3b", size_gib: 2.2 }],
      error: "Warmup required",
    },
  ],
  gpu_memory_gib: 8,
};

describe("LlmModelSelector", () => {
  it("renders provider and model options from the catalog", () => {
    render(
      <LlmModelSelector
        label="Generator provider"
        modelLabel="Generator model"
        catalog={catalog}
        selection={{ provider: "openai", model: "gpt-4o-mini" }}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Generator provider")).toHaveValue("openai");
    expect(screen.getByLabelText("Generator model")).toHaveValue("gpt-4o-mini");
    expect(screen.getByRole("option", { name: "gpt-4.1-mini" })).toBeInTheDocument();
  });

  it("shows Ollama model sizes and provider metadata", () => {
    render(
      <LlmModelSelector
        label="Provider"
        catalog={catalog}
        selection={{ provider: "ollama", model: "qwen2.5:3b" }}
        onChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("option", { name: "qwen2.5:3b (2.2 GiB)" })).toBeInTheDocument();
    expect(screen.getByText("GPU memory: 8 GiB; Warmup required")).toBeInTheDocument();
  });

  it("selects the first model for the new provider when provider changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <LlmModelSelector
        label="Provider"
        catalog={catalog}
        selection={{ provider: "openai", model: "gpt-4o-mini" }}
        onChange={onChange}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Provider"), "ollama");

    expect(onChange).toHaveBeenCalledWith({ provider: "ollama", model: "qwen2.5:3b" });
  });

  it("returns the first catalog model for a provider", () => {
    expect(getDefaultCatalogModel(catalog, "openai")).toBe("gpt-4o-mini");
    expect(getDefaultCatalogModel(catalog, "ollama")).toBe("qwen2.5:3b");
  });
});
