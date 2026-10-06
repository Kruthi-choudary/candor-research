import { useEffect, useState } from "react";
import { api, type EvalSummary } from "../lib/api";
import { formatPercent } from "../lib/format";

export function Evaluation() {
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getEvalSummary().then(setSummary).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <div className="px-10 py-10 text-sm text-negative">{error}</div>;
  }
  if (!summary) {
    return <div className="px-10 py-10 text-sm text-text-faint">Loading…</div>;
  }

  const { baseline, structured } = summary.citation_grounding;

  return (
    <div className="mx-auto max-w-4xl px-10 py-10">
      <h1 className="text-2xl font-medium text-text">Evaluation</h1>
      <p className="mt-1 text-sm text-text-muted">
        How Candor's citation-grounded generation was measured, and what changed.
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-medium text-text">Citation-grounding experiment</h2>
        <p className="mt-1 text-xs text-text-faint">
          Free-text citations (regex-parsed "quote" [mm:ss] markers) vs a JSON-schema-constrained
          response that forces every claim to carry an exact, copy-verbatim citation.
        </p>
        <div className="mt-4 overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-raised text-left text-xs uppercase tracking-wide text-text-faint">
                <th className="px-4 py-3">Metric</th>
                <th className="px-4 py-3">{baseline?.label ?? "Baseline"}</th>
                <th className="px-4 py-3">{structured?.label ?? "Structured"}</th>
              </tr>
            </thead>
            <tbody className="text-text-muted">
              <Row label="Schema compliance" a={formatPercent(baseline?.schema_compliance)} b={formatPercent(structured?.schema_compliance)} />
              <Row label="Citation accuracy" a={formatPercent(baseline?.citation_accuracy)} b={formatPercent(structured?.citation_accuracy)} highlight />
              <Row label="Total citations" a={String(baseline?.total_citations ?? "—")} b={String(structured?.total_citations ?? "—")} />
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-medium text-text">Claim-extraction coverage</h2>
        <p className="mt-1 text-xs text-text-faint">
          Precision/recall/F1 against hand-labeled ground-truth claims — approximate text-similarity
          matching, read per-call before trusting the aggregate.
        </p>
        {summary.claim_coverage ? (
          <div className="mt-4 flex flex-col gap-3">
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Avg precision" value={formatPercent(summary.claim_coverage.avg_precision)} />
              <Stat label="Avg recall" value={formatPercent(summary.claim_coverage.avg_recall)} />
              <Stat label="Avg F1" value={formatPercent(summary.claim_coverage.avg_f1)} />
            </div>
            <div className="text-xs text-text-faint">
              {summary.claim_coverage.calls_evaluated} call(s) labeled
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-faint">
            No calls hand-labeled yet. Run{" "}
            <code className="text-text-muted">python -m src.eval.scaffold_labels</code> and{" "}
            <code className="text-text-muted">check_claim_coverage</code> to populate this.
          </div>
        )}
      </section>
    </div>
  );
}

function Row({ label, a, b, highlight }: { label: string; a: string; b: string; highlight?: boolean }) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3 text-text-faint">{label}</td>
      <td className="px-4 py-3">{a}</td>
      <td className={`px-4 py-3 ${highlight ? "font-medium text-mint" : ""}`}>{b}</td>
    </tr>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-raised px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-text-faint">{label}</div>
      <div className="mt-1 text-lg font-medium text-text">{value}</div>
    </div>
  );
}
