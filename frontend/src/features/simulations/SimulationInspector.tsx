import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { KeyValueList } from "@/components/common/KeyValueList";
import { stringifyJson } from "@/utils/format";
import type {
  EvidenceLedger,
  SimulationReadWithState,
  SimulationTokenUsage,
  SimulationTurnResponse
} from "@/api/types";

type CoachAdviceRecord = Record<string, unknown>;

type PositionAssessmentRecord = {
  target_value?: string;
  reservation_value?: string;
  current_offer_assessment?: string;
  zopa_comment?: string;
};

type CoachSourceRecord = {
  title: string;
  author: string;
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

function getTokenUsage(
  simulation: SimulationReadWithState,
  latestTurn: SimulationTurnResponse | null
): SimulationTokenUsage | null {
  if (latestTurn?.token_usage) {
    return latestTurn.token_usage;
  }

  const persisted = simulation.negotiation_state?.data?.token_usage;
  return isRecord(persisted) ? (persisted as SimulationTokenUsage) : null;
}

function getEvidenceLedgers(
  simulation: SimulationReadWithState,
  latestTurn: SimulationTurnResponse | null
): EvidenceLedger[] {
  if (Array.isArray(latestTurn?.evidence_ledgers) && latestTurn.evidence_ledgers.length > 0) {
    return latestTurn.evidence_ledgers;
  }
  return Array.isArray(simulation.evidence_ledgers) ? simulation.evidence_ledgers : [];
}

function asObjectList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function getCoachSources(value: unknown): CoachSourceRecord[] {
  return asObjectList(value).slice(0, 3).map((source) => ({
    title: getString(source.document_title) ?? "Missing Title",
    author: getString(source.document_author) ?? "Missing Author"
  }));
}

function CollapsibleJsonPreview({ value, testId }: { value: string; testId: string }) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = value.split(/\r?\n/).length > 5;
  const isCollapsed = canExpand && !expanded;

  return (
    <div className="mt-3">
      <div
        data-testid={testId}
        className={[
          "rounded-xl bg-slate-950",
          isCollapsed ? "max-h-[6.25rem] overflow-hidden" : ""
        ].join(" ")}
      >
        <pre className="overflow-x-auto p-3 text-xs leading-5 text-slate-100">{value}</pre>
      </div>
      {canExpand ? (
        <div className="mt-2 flex justify-end">
          <Button
            type="button"
            className="px-3 py-1.5"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Show less" : "Show more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function EvidenceLedgerCard({ ledgers }: { ledgers: EvidenceLedger[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="min-w-0">
      <h2 className="text-lg font-semibold text-slate-950">Evidence Ledger</h2>
      {expanded ? (
        !ledgers.length ? (
          <p className="mt-3 text-sm text-slate-600">
            Evidence records will appear after agent outputs are captured for a turn.
          </p>
        ) : (
          <div className="mt-4 grid gap-4">
            {ledgers.map((ledger) => {
              const pipeline = isRecord(ledger.pipeline) ? ledger.pipeline : {};
              const sources = asObjectList(ledger.sources);
              const qualityChecks = asObjectList(ledger.quality_checks);
              const steps = asObjectList(pipeline.steps);
              return (
                <section key={`${ledger.id}-${ledger.agent_name}`} className="grid gap-3 rounded-lg border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-slate-900">{ledger.agent_name}</h3>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                      turn {ledger.turn_index} / {ledger.visibility_level}
                    </span>
                  </div>

                  {steps.length ? (
                    <div className="grid gap-1">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Pipeline</div>
                      <div className="flex flex-wrap gap-2">
                        {steps.map((step, index) => (
                          <span key={`${ledger.id}-step-${index}`} className="rounded bg-slate-50 px-2 py-1 text-xs text-slate-700">
                            <span>{String(step.name ?? "step")}</span>
                            <span className="text-slate-400"> / </span>
                            <span>{String(step.status ?? "unknown")}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {sources.length ? (
                    <div className="grid gap-2">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Sources</div>
                      {sources.slice(0, 3).map((source, index) => (
                        <div key={`${ledger.id}-source-${index}`} className="rounded bg-slate-50 p-2 text-xs text-slate-700">
                          <div className="font-medium text-slate-900">
                            {String(source.source ?? `Chunk ${String(source.document_chunk_id ?? index + 1)}`)}
                          </div>
                          <p className="mt-1 whitespace-pre-wrap leading-5">{String(source.excerpt ?? "")}</p>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {qualityChecks.length ? (
                    <div className="grid gap-1">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Quality checks</div>
                      {qualityChecks.map((check, index) => (
                        <p key={`${ledger.id}-check-${index}`} className="text-xs text-slate-700">
                          {String(check.name ?? "check")}: {String(check.verdict ?? "unknown")}
                        </p>
                      ))}
                    </div>
                  ) : null}

                  <details>
                    <summary className="cursor-pointer text-xs font-medium text-slate-600">Raw debug</summary>
                    <pre className="mt-2 overflow-x-auto rounded bg-slate-950 p-2 text-xs text-slate-100">
                      {stringifyJson({
                        output_summary: ledger.output_summary,
                        token_usage: ledger.token_usage,
                        raw_debug: ledger.raw_debug
                      })}
                    </pre>
                  </details>
                </section>
              );
            })}
          </div>
        )
      ) : null}
      <div className="mt-2 flex justify-end">
        <Button
          type="button"
          className="px-3 py-1.5"
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "Show less" : "Show more"}
        </Button>
      </div>
    </Card>
  );
}

function CoachGuidanceCard({
  advice,
  coachTotalTokens
}: {
  advice: CoachAdviceRecord | null;
  coachTotalTokens: number | null;
}) {
  if (!advice) {
    return (
      <Card className="min-w-0">
        <h2 className="text-lg font-semibold text-slate-950">Coach Guidance</h2>
        {coachTotalTokens !== null ? (
          <p className="mt-1 text-sm text-slate-500">{coachTotalTokens} total coach tokens</p>
        ) : null}
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
  const sources = getCoachSources(advice.sources);
  const positionAssessment = isRecord(advice.position_assessment)
    ? (advice.position_assessment as PositionAssessmentRecord)
    : null;

  return (
    <Card className="min-w-0">
      <h2 className="text-lg font-semibold text-slate-950">Coach Guidance</h2>
      {coachTotalTokens !== null ? (
        <p className="mt-1 text-sm text-slate-500">{coachTotalTokens} total coach tokens</p>
      ) : null}
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

        {sources.length ? (
          <section className="grid gap-2">
            <h3 className="text-sm font-semibold text-slate-900">Sources</h3>
            <ul className="grid gap-2">
              {sources.map((source, index) => (
                <li key={`${source.title}-${source.author}-${index}`} className="rounded-xl bg-slate-50 px-3 py-2">
                  <div className="text-sm font-medium text-slate-900">{source.title}</div>
                  <div className="mt-1 text-sm text-slate-600">{source.author}</div>
                </li>
              ))}
            </ul>
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
  const tokenUsage = getTokenUsage(simulation, latestTurn);
  const evidenceLedgers = getEvidenceLedgers(simulation, latestTurn);

  return (
    <div className="grid min-w-0 w-full gap-4">
      <CoachGuidanceCard advice={coachAdvice} coachTotalTokens={tokenUsage?.coach_total ?? null} />

      <EvidenceLedgerCard ledgers={evidenceLedgers} />

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
        <CollapsibleJsonPreview value={stringifyJson(state.data)} testId="negotiation-data-preview" />
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
