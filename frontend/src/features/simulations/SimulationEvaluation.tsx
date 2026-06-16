type EvaluationRecord = Record<string, unknown>;

function asString(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "Not provided";
  }
  return String(value);
}

function asStringList(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => (item === null || item === undefined ? "" : String(item).trim()))
    .filter(Boolean);
}

function EvaluationList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="grid gap-1">
      <p className="font-medium text-slate-900">{title}</p>
      {items.length ? (
        items.map((item) => (
          <p key={`${title}-${item}`} className="text-sm text-slate-700">
            {item}
          </p>
        ))
      ) : (
        <p className="text-sm text-slate-600">Not provided</p>
      )}
    </div>
  );
}

export function SimulationEvaluation({
  evaluation,
  evaluatorTotalTokens = null
}: {
  evaluation: EvaluationRecord;
  evaluatorTotalTokens?: number | null;
}) {
  return (
    <section className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <h2 className="text-base font-semibold text-slate-950">Final evaluation</h2>
      <p className="text-sm text-slate-700">Overall score: {asString(evaluation.overall_score)}</p>
      <p className="text-sm text-slate-700">Goal achievement: {asString(evaluation.goal_achievement)}</p>
      <EvaluationList title="Strengths" items={asStringList(evaluation.strengths)} />
      <EvaluationList title="Mistakes" items={asStringList(evaluation.mistakes)} />
      <p className="text-sm text-slate-700">Concession quality: {asString(evaluation.concession_quality)}</p>
      <p className="text-sm text-slate-700">Communication quality: {asString(evaluation.communication_quality)}</p>
      <p className="text-sm text-slate-700">Outcome quality: {asString(evaluation.outcome_quality)}</p>
      <EvaluationList title="Lessons" items={asStringList(evaluation.lessons)} />
      <p className="text-sm text-slate-700">Reasoning: {asString(evaluation.reasoning)}</p>
      <p className="text-sm text-slate-700">Confidence: {asString(evaluation.confidence)}</p>
      <EvaluationList title="Missing information" items={asStringList(evaluation.missing_information)} />
      {evaluatorTotalTokens !== null ? (
        <p className="text-xs font-medium text-slate-500">{evaluatorTotalTokens} total evaluator tokens</p>
      ) : null}
    </section>
  );
}
