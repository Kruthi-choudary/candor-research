import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { resources, useAnalysisResource } from "../hooks/useAnalysis";
import { DataSourceNote } from "../components/DataStatus";
import { formatPercent } from "../lib/format";
import { EmptyState } from "../components/States";

export function Evaluation() {
  const evaluation = useAnalysisResource(resources.evaluation);
  const summary = evaluation.data!;
  const baseline = summary?.citation_grounding.baseline;
  const structured = summary?.citation_grounding.structured;
  const coverage = summary?.claim_coverage;
  return (
    <div className="container page reveal">
      <div className="evaluation-lead">
        <header>
          <p className="eyebrow muted">Methodology & evaluation</p>
          <h1 className="page-title">Evidence over assertion.</h1>
          <p className="page-description">
            These benchmarks measure citation matching and claim extraction.
            Executive-specific communication changes are not yet evaluated.
          </p>
        </header>
        <div className="notice">
          <strong>Two questions. Two different checks.</strong>
          <p>
            Does the citation match the source? And did the system extract the
            right claims? A high score on one does not answer the other.
          </p>
        </div>
      </div>
      <DataSourceNote sources={{ "evaluation results": evaluation.source }} />
      <>
        <section
          className="section-space rule-top"
          aria-labelledby="citation-heading"
        >
          <div className="section-top">
            <div>
              <p className="eyebrow muted mb-2">01 / Citation matching</p>
              <h2 className="section-heading" id="citation-heading">
                A more traceable output.
              </h2>
            </div>
            <span className="badge">
              {evaluation.source === "demo"
                ? "Bundled benchmark snapshot"
                : "Recorded benchmark"}
            </span>
          </div>
          <p className="muted max-w-3xl mb-6">
            A comparison of free-text generation with structured JSON output.
            The checker uses approximate quote matching near a timestamp; these
            results measure citation matching, rather than factual correctness.
          </p>
          {!baseline && !structured ? (
            <EmptyState
              title="No citation benchmark recorded."
              description="Results will appear here when the evaluation service has a recorded run."
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <caption>
                  {evaluation.source === "demo"
                    ? "Demonstration snapshot of recorded project results; these are not live-fetched benchmark values."
                    : "Values below are fetched from archived evaluation runs."}
                  {" "}These experiments do not evaluate newly regenerated reports.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Measure</th>
                    <th scope="col">
                      {baseline?.label ?? "Baseline unavailable"}
                    </th>
                    <th scope="col">
                      {structured?.label ?? "Structured run unavailable"}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <BenchmarkRow
                    label="Output-format compliance"
                    a={baseline?.schema_compliance}
                    b={structured?.schema_compliance}
                  />
                  <BenchmarkRow
                    label="Citation-match rate"
                    a={baseline?.citation_accuracy}
                    b={structured?.citation_accuracy}
                  />
                  <tr>
                    <th scope="row">Citations evaluated</th>
                    <td className="numeric">
                      {baseline?.total_citations ?? "—"}
                    </td>
                    <td className="numeric">
                      {structured?.total_citations ?? "—"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
          <p className="caption muted mt-4">
            The baseline and structured runs use different citation-parsing and
            timestamp-matching procedures. Treat this as an implementation
            comparison, not an isolated experiment proving schema alone caused
            the change.
          </p>
        </section>
        <section
          className="section-space rule-top"
          aria-labelledby="coverage-heading"
        >
          <div className="section-top">
            <div>
              <p className="eyebrow muted mb-2">02 / Claim coverage</p>
              <h2 className="section-heading" id="coverage-heading">
                What made it into the brief?
              </h2>
            </div>
            <span className="badge badge-warning">Human review incomplete</span>
          </div>
          <p className="muted max-w-3xl">
            Generated claims are compared with labelled claims using approximate
            text similarity. Precision measures how many generated claims match
            the labels; recall measures how many labelled claims were found. F1
            balances both.
          </p>
          {coverage ? (
            <>
              <div className="metric-row">
                <div className="metric">
                  <p className="metric-value">
                    {formatPercent(coverage.avg_precision)}
                  </p>
                  <p className="metric-label">Mean precision</p>
                </div>
                <div className="metric">
                  <p className="metric-value">
                    {formatPercent(coverage.avg_recall)}
                  </p>
                  <p className="metric-label">Mean recall</p>
                </div>
                <div className="metric">
                  <p className="metric-value">
                    {formatPercent(coverage.avg_f1)}
                  </p>
                  <p className="metric-label">Mean F1 score</p>
                </div>
              </div>
              <div className="table-wrap mt-7">
                <table className="data-table">
                  <caption>
                    Per-call results · {coverage.calls_evaluated} labelled calls
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Earnings call</th>
                      <th scope="col">Precision</th>
                      <th scope="col">Recall</th>
                      <th scope="col">F1</th>
                      <th scope="col">
                        <span className="sr-only">Report</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {coverage.results.map((r) => (
                      <tr key={`${r.ticker}/${r.quarter}`}>
                        <th scope="row">
                          {r.ticker}{" "}
                          <span className="font-normal muted">
                            / {r.quarter.replace("_", " ")}
                          </span>
                        </th>
                        <td>{formatPercent(r.precision)}</td>
                        <td>{formatPercent(r.recall)}</td>
                        <td>{formatPercent(r.f1)}</td>
                        <td>
                          <Link
                            className="claim-action-link"
                            to={`/app/calls/${r.ticker}/${r.quarter.replace("_", "-")}`}
                            aria-label={`Open ${r.ticker} ${r.quarter} report`}
                          >
                            <ArrowUpRight size={16} aria-hidden="true" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <EmptyState
              title="Claim coverage has not been recorded."
              description="Coverage results require labelled reference claims and a completed evaluation run."
            />
          )}
          <div className="notice mt-6">
            <p>
              Coverage scores describe the archived generation run, not newly
              regenerated reports. Citation validity and claim correctness require
              separate assessment.
            </p>
            <strong>Label provenance matters.</strong>
            <p>
              The repository documents the Apple reference set as independently
              human-labelled. The Meta, Microsoft and Nvidia reference files are
              marked AI-drafted, pending human review. Their aggregate is not an
              independently human-validated quality score.
            </p>
            <p>
              These provenance notes describe the current dataset; the API does
              not supply per-label review status.
            </p>
          </div>
        </section>
        <section className="section-space rule-top">
          <p className="eyebrow muted mb-3">
            03 / Reading the results responsibly
          </p>
          <div className="intro-grid">
            <h2 className="editorial editorial-heading mt-0">
              The source is the beginning.
              <br />
              Judgment is still yours.
            </h2>
            <div>
              <p className="muted">
                Matching citations can still accompany incomplete, misleading or
                unsupported interpretations. Transcription errors and
                sentiment-based quote selection can also leave important
                information out of a brief.
              </p>
              <Link to="/app" className="text-link mt-5">
                Inspect the research yourself{" "}
                <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>
      </>
    </div>
  );
}

function BenchmarkRow({
  label,
  a,
  b,
}: {
  label: string;
  a?: number | null;
  b?: number | null;
}) {
  return (
    <tr>
      <th scope="row">{label}</th>
      {[a, b].map((value, i) => (
        <td key={i}>
          <span className="numeric">{formatPercent(value)}</span>
          {value != null && (
            <div className="benchmark-bar" aria-hidden="true">
              <span
                style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
              />
            </div>
          )}
        </td>
      ))}
    </tr>
  );
}
