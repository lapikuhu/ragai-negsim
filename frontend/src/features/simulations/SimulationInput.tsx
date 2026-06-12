import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Textarea } from "@/components/ui/Field";
import { SimulationEvaluation } from "@/features/simulations/SimulationEvaluation";

type EvaluationRecord = Record<string, unknown>;

export function SimulationInput({
  disabled,
  disabledMessage,
  onSubmit,
  canEvaluate = false,
  evaluation = null,
  isEvaluationVisible = false,
  onEvaluate,
  evaluationUnavailableMessage
}: {
  disabled?: boolean;
  disabledMessage?: string | null;
  onSubmit: (message: string) => Promise<void>;
  canEvaluate?: boolean;
  evaluation?: EvaluationRecord | null;
  isEvaluationVisible?: boolean;
  onEvaluate?: () => void;
  evaluationUnavailableMessage?: string | null;
}) {
  const [message, setMessage] = useState("");

  return (
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
          disabled={disabled}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Write the next negotiation message..."
        />
      </Field>
      {disabledMessage ? <p className="text-sm text-slate-600">{disabledMessage}</p> : null}
      {evaluationUnavailableMessage ? (
        <p className="text-sm text-slate-600">{evaluationUnavailableMessage}</p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" disabled={!canEvaluate} onClick={onEvaluate}>
          Evaluate
        </Button>
        <Button type="submit" disabled={disabled || !message.trim()}>
          Send turn
        </Button>
      </div>
      {isEvaluationVisible && evaluation ? <SimulationEvaluation evaluation={evaluation} /> : null}
    </form>
  );
}
