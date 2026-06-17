import { useState } from "react";
import type { LLMModelCatalogResponse, LLMProvider, LLMSelection } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field, Select, Textarea } from "@/components/ui/Field";
import { SimulationEvaluation } from "@/features/simulations/SimulationEvaluation";

type EvaluationRecord = Record<string, unknown>;
type ProxyDuration = "this_turn" | "remainder";
type ProxyPersonaOption = { id: number; name: string };

export function SimulationInput({
  disabled,
  disabledMessage,
  onSubmit,
  onProxySubmit,
  llmCatalog,
  llmCatalogError,
  proxyPersonaOptions = [],
  isProxyActive = false,
  proxyActiveLabel,
  onTakeControl,
  proxyBusy = false,
  canEvaluate = false,
  evaluation = null,
  evaluatorTotalTokens = null,
  isEvaluationVisible = false,
  onEvaluate,
  evaluationUnavailableMessage
}: {
  disabled?: boolean;
  disabledMessage?: string | null;
  onSubmit: (message: string) => Promise<void>;
  onProxySubmit?: (input: { personaId: number | null; duration: ProxyDuration; llmSelection: LLMSelection }) => Promise<void>;
  llmCatalog?: LLMModelCatalogResponse;
  llmCatalogError?: string | null;
  proxyPersonaOptions?: ProxyPersonaOption[];
  isProxyActive?: boolean;
  proxyActiveLabel?: string | null;
  onTakeControl?: () => Promise<void>;
  proxyBusy?: boolean;
  canEvaluate?: boolean;
  evaluation?: EvaluationRecord | null;
  evaluatorTotalTokens?: number | null;
  isEvaluationVisible?: boolean;
  onEvaluate?: () => void;
  evaluationUnavailableMessage?: string | null;
}) {
  const [message, setMessage] = useState("");
  const [isProxyDialogOpen, setIsProxyDialogOpen] = useState(false);
  const [proxyPersonaId, setProxyPersonaId] = useState("");
  const [proxyDuration, setProxyDuration] = useState<ProxyDuration>("this_turn");
  const [proxyLlm, setProxyLlm] = useState<LLMSelection>({
    provider: "openai",
    model: getDefaultCatalogModel(llmCatalog, "openai") ?? ""
  });
  const proxyProviderCatalog = llmCatalog?.providers.find((provider) => provider.provider === proxyLlm.provider);
  const proxyModels = proxyProviderCatalog?.models ?? [];
  const canConfirmProxy = Boolean(onProxySubmit) && Boolean(proxyLlm.model);

  return (
    <>
      <form
        className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!message.trim()) {
            return;
          }
          await onSubmit(message);
          setMessage("");
        }}
      >
        <Field label="Your next turn">
          <Textarea
            value={message}
            disabled={disabled || isProxyActive}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Write the next negotiation message..."
          />
        </Field>
        {proxyActiveLabel ? (
          <div className="flex items-center justify-between gap-3 rounded-xl border border-teal-200 bg-teal-50 px-3 py-2">
            <p className="text-sm font-medium text-teal-900">{proxyActiveLabel}</p>
            {onTakeControl ? (
              <Button type="button" variant="secondary" disabled={proxyBusy} onClick={() => void onTakeControl()}>
                Take Control
              </Button>
            ) : null}
          </div>
        ) : null}
        {disabledMessage ? <p className="text-sm text-slate-600">{disabledMessage}</p> : null}
        {evaluationUnavailableMessage ? (
          <p className="text-sm text-slate-600">{evaluationUnavailableMessage}</p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button type="button" disabled={!canEvaluate} onClick={onEvaluate}>
            Evaluate
          </Button>
          {isProxyActive ? null : (
            <Button
              type="button"
              variant="secondary"
              disabled={disabled || proxyBusy || !onProxySubmit}
              onClick={() => setIsProxyDialogOpen(true)}
            >
              Use Proxy
            </Button>
          )}
          <Button type="submit" disabled={disabled || isProxyActive || !message.trim()}>
            Send turn
          </Button>
        </div>
        {isEvaluationVisible && evaluation ? (
          <SimulationEvaluation evaluation={evaluation} evaluatorTotalTokens={evaluatorTotalTokens} />
        ) : null}
      </form>

      {isProxyDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Use Proxy"
            className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"
          >
            <div className="grid gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Use Proxy</h2>
                <p className="mt-1 text-sm text-slate-600">Choose a persona and how long the proxy should take over.</p>
              </div>
              <Field label="Persona">
                <Select value={proxyPersonaId} onChange={(event) => setProxyPersonaId(event.target.value)}>
                  <option value="">None (Neutral)</option>
                  {proxyPersonaOptions.map((persona) => (
                    <option key={persona.id} value={persona.id}>
                      {persona.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <Field label="Provider">
                  <Select
                    value={proxyLlm.provider}
                    onChange={(event) => {
                      const provider = event.target.value as LLMProvider;
                      setProxyLlm({ provider, model: getDefaultCatalogModel(llmCatalog, provider) ?? "" });
                    }}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="ollama">Ollama</option>
                  </Select>
                </Field>
                <Field label="Model">
                  <Select
                    value={proxyLlm.model}
                    disabled={!proxyModels.length}
                    onChange={(event) => setProxyLlm((current) => ({ ...current, model: event.target.value }))}
                  >
                    <option value="">{proxyModels.length ? "Select model" : "No models available"}</option>
                    {proxyModels.map((model) => (
                      <option key={model.name} value={model.name}>
                        {model.name}
                        {proxyLlm.provider === "ollama" && typeof model.size_gib === "number" ? ` (${model.size_gib} GiB)` : ""}
                      </option>
                    ))}
                  </Select>
                </Field>
                {proxyLlm.provider === "ollama" ? (
                  <p className="text-xs text-slate-500">
                    GPU memory: {typeof llmCatalog?.gpu_memory_gib === "number" ? `${llmCatalog.gpu_memory_gib} GiB` : "unknown"}
                    {proxyProviderCatalog?.error ? `; ${proxyProviderCatalog.error}` : ""}
                  </p>
                ) : null}
                {llmCatalogError ? <p className="text-xs text-amber-700">{llmCatalogError}</p> : null}
              </div>
              <fieldset className="grid gap-2">
                <legend className="text-sm font-medium text-slate-700">Duration</legend>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="radio"
                    name="proxy-duration"
                    checked={proxyDuration === "this_turn"}
                    onChange={() => setProxyDuration("this_turn")}
                  />
                  <span>For this turn</span>
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="radio"
                    name="proxy-duration"
                    checked={proxyDuration === "remainder"}
                    onChange={() => setProxyDuration("remainder")}
                  />
                  <span>For the remainder of the negotiation</span>
                </label>
              </fieldset>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="ghost" onClick={() => setIsProxyDialogOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="button"
                  disabled={!canConfirmProxy}
                  onClick={async () => {
                    if (!onProxySubmit || !proxyLlm.model) {
                      return;
                    }
                    setIsProxyDialogOpen(false);
                    await onProxySubmit({
                      personaId: proxyPersonaId ? Number(proxyPersonaId) : null,
                      duration: proxyDuration,
                      llmSelection: proxyLlm
                    });
                  }}
                >
                  Confirm Proxy
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function getDefaultCatalogModel(catalog: LLMModelCatalogResponse | undefined, provider: LLMProvider) {
  return catalog?.providers.find((entry) => entry.provider === provider)?.models[0]?.name ?? null;
}
