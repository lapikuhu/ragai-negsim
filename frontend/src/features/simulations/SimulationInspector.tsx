import { Card } from "@/components/ui/Card";
import { KeyValueList } from "@/components/common/KeyValueList";
import { stringifyJson } from "@/utils/format";
import type { SimulationReadWithState, SimulationTurnResponse } from "@/api/types";

type CoachAdviceRecord = Record<string, unknown>;

type PositionAssessmentRecord = {
  target_value?: string;
  reservation_value?: string;
  current_offer_assessment?: string;
  zopa_comment?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getCoachAdvice(
  simulation: SimulationReadWithState,
  latestTurn: SimulationTurnResponse | null
): CoachAdviceRecord | null {
  if (isRecord(latestTurn?.coach_advice) && Object.keys(latestTurn.coach_advice).length > 0) {
    return latestTurn.coach_advice;
  }

  const persisted = simulation.negotiation_state?.data?.coach_advice;
  if (isRecord(persisted) && Object.keys(persisted).length > 0) {
    return persisted;
  }

  return null;
}

function getString(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

function getStringList(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
}

function CoachGuidanceCard({ advice }: { advice: CoachAdviceRecord | null }) {
  if (!advice) {
    return (
      <Card className="min-w-0">
        <h2 className="text-lg font-semibold text-slate-950">Coach guidance</h2>
        <p className="mt-3 text-sm text-slate-600">
          Coach guidance will appear after a turn produces public coach output.
        </p>
      </Card>
    );
  }

  const summary = getString(advice.summary);
  const suggestedResponse = getString(advice.suggested_response);
  const recommendedNextMove = getString(advice.recommended_next_move);
  const confidence = getString(advice.confidence);
  const reasoning = getString(advice.reasoning);
  const risks = getStringList(advice.risks);
  const missingInformation = getStringList(advice.missing_information);
  const positionAssessment = isRecord(advice.position_assessment)
    ? (advice.position_assessment as PositionAssessmentRecord)
    : null;

  return (
    <Card className="min-w-0">
      <h2 className="text-lg font-semibold text-slate-950">Coach guidance</h2>
      <div className="mt-4 grid gap-4">
        {summary ? (
          <section className="grid gap-1">
            <h3 className="text-sm font-semibold text-slate-900">Summary</h3>
            <p className="text-sm leading-6 text-slate-700">{summary}</p>
          </section>
        ) : null}

        {suggestedResponse ? (
          <section className="grid gap-1">
            <h3 className="text-sm font-semibold text-slate-900">Suggested response</h3>
            <p className="whitespace-pre-wrap rounded-xl bg-slate-50 p-3 text-sm leading-6 text-slate-700">
              {suggestedResponse}
            </p>
          </section>
        ) : null}

        {recommendedNextMove || confidence ? (
          <section className="grid gap-2 sm:grid-cols-2">
            {recommendedNextMove ? (
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Next move</div>
                <div className="mt-1 text-sm text-slate-800">{recommendedNextMove}</div>
              </div>
            ) : null}
            {confidence ? (
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Confidence</div>
                <div className="mt-1 text-sm text-slate-800">{confidence}</div>
              </div>
            ) : null}
          </section>
        ) : null}

        {positionAssessment ? (
          <section className="grid gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Position assessment</h3>
            <KeyValueList
              items={[
                { label: "Target value", value: positionAssessment.target_value ?? "Not provided" },
                { label: "Reservation value", value: positionAssessment.reservation_value ?? "Not provided" },
                {
                  label: "Current offer",
                  value: positionAssessment.current_offer_assessment ?? "Not provided"
                },
                { label: "ZOPA comment", value: positionAssessment.zopa_comment ?? "Not provided" }
              ]}
            />
          </section>
        ) : null}

        {risks.length ? (
          <section className="grid gap-1">
            <h3 className="text-sm font-semibold text-slate-900">Risks</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
              {risks.map((risk) => (
                <li key={risk}>{risk}</li>
              ))}
            </ul>
          </section>
        ) : null}

        {missingInformation.length ? (
          <section className="grid gap-1">
            <h3 className="text-sm font-semibold text-slate-900">Missing information</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
              {missingInformation.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        ) : null}

        {reasoning ? (
          <section className="grid gap-1">
            <h3 className="text-sm font-semibold text-slate-900">Reasoning</h3>
            <p className="text-sm leading-6 text-slate-700">{reasoning}</p>
          </section>
        ) : null}
      </div>
    </Card>
  );
}

export function SimulationInspector({
  simulation,
  latestTurn
}: {
  simulation: SimulationReadWithState;
  latestTurn: SimulationTurnResponse | null;
}) {
  const state = simulation.negotiation_state ?? { current_phase: null, user_side: null, data: {} };
  const coachAdvice = getCoachAdvice(simulation, latestTurn);

  return (
    <div className="grid min-w-0 w-full gap-4">
      <CoachGuidanceCard advice={coachAdvice} />

      <Card className="min-w-0">
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

      <Card className="min-w-0">
        <h2 className="text-lg font-semibold text-slate-950">Negotiation data</h2>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-100">
          {stringifyJson(state.data)}
        </pre>
      </Card>

      <Card className="min-w-0">
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
                  final_evaluation: latestTurn.final_evaluation
                }
              : { note: "Submit a turn to inspect the latest public outputs." }
          )}
        </pre>
      </Card>
    </div>
  );
}
