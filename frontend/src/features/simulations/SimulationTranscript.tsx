import { Card } from "@/components/ui/Card";
import { formatDateTime } from "@/utils/format";
import type { SimulationReadWithState } from "@/api/types";

export function SimulationTranscript({ simulation }: { simulation: SimulationReadWithState }) {
  const messages = simulation.messages ?? [];

  return (
    <Card className="grid gap-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">Transcript</h2>
        <p className="mt-1 text-sm text-slate-600">Real turn history from the simulation state payload.</p>
      </div>

      <div className="grid gap-2">
        {messages.length ? (
          messages.map((message, index) => (
            <div
              key={`${message.timestamp ?? index}-${message.role}`}
              className="self-start rounded-2xl bg-slate-50 px-4 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <strong className="text-sm capitalize text-slate-900">{message.role}</strong>
                <span className="text-xs text-slate-500">{formatDateTime(message.timestamp)}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{message.content}</p>
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-600">No turns yet. Start the simulation to generate an opening state.</p>
        )}
      </div>
    </Card>
  );
}
