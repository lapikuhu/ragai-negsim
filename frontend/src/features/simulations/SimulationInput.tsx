import { useState } from "react";
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
  onProxySubmit?: (input: { personaId: number | null; duration: ProxyDuration }) => Promise<void>;
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
                  onClick={async () => {
                    if (!onProxySubmit) {
                      return;
                    }
                    setIsProxyDialogOpen(false);
                    await onProxySubmit({
                      personaId: proxyPersonaId ? Number(proxyPersonaId) : null,
                      duration: proxyDuration
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
