import { Card } from "@/components/ui/Card";
import { KeyValueList } from "@/components/common/KeyValueList";
import { stringifyJson } from "@/utils/format";
import type { SimulationReadWithState, SimulationTurnResponse } from "@/api/types";

export function SimulationInspector({
  simulation,
  latestTurn
}: {
  simulation: SimulationReadWithState;
  latestTurn: SimulationTurnResponse | null;
}) {
  const state = simulation.negotiation_state ?? { current_phase: null, user_side: null, data: {} };

  return (
    <div className="grid gap-4">
      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Simulation state</h2>
        <div className="mt-4">
          <KeyValueList
            items={[
              { label: "Phase", value: state.current_phase ?? "Not started" },
              { label: "User side", value: state.user_side ?? "Unassigned" },
              { label: "Teacher reviewed", value: simulation.teacher_reviewed ? "Yes" : "No" },
              { label: "Teacher feedback", value: simulation.teacher_feedback ?? "No feedback yet" }
            ]}
          />
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Negotiation data</h2>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-100">
          {stringifyJson(state.data)}
        </pre>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Latest turn outputs</h2>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-100">
          {stringifyJson(
            latestTurn
              ? {
                  phase: latestTurn.phase,
                  should_pause: latestTurn.should_pause,
                  pause_reason: latestTurn.pause_reason,
                  coach_advice: latestTurn.coach_advice,
                  counterpart_response: latestTurn.counterpart_response,
                  event_log: latestTurn.event_log
                }
              : { note: "Submit a turn to inspect coach advice and event output." }
          )}
        </pre>
      </Card>
    </div>
  );
}
