import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Textarea } from "@/components/ui/Field";

export function SimulationInput({
  disabled,
  disabledMessage,
  onSubmit
}: {
  disabled?: boolean;
  disabledMessage?: string | null;
  onSubmit: (message: string) => Promise<void>;
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
      <div className="flex justify-end">
        <Button type="submit" disabled={disabled || !message.trim()}>
          Send turn
        </Button>
      </div>
    </form>
  );
}
