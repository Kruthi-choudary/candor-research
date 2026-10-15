import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, ArrowUpRight } from "lucide-react";
import { api, type CallSummary } from "../lib/api";
import { formatDate, formatPercent } from "../lib/format";
import { TickerBadge } from "../components/TickerBadge";
import { SentimentBar } from "../components/SentimentBar";
import { EmptyState, ErrorState, LoadingState } from "../components/States";

export function Dashboard() {
  const [calls, setCalls] = useState<CallSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [company, setCompany] = useState("All companies");
  useEffect(() => {
    let cancelled = false;
    api
      .listCalls()
      .then((d) => {
        if (!cancelled) setCalls(d.calls);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);
  const sorted = useMemo(
    () =>
      [...(calls ?? [])].sort(
        (a, b) =>
          (b.call_date ?? "").localeCompare(a.call_date ?? "") ||
          a.ticker.localeCompare(b.ticker),
      ),
    [calls],
  );
  const companies = [...new Set(sorted.map((c) => c.ticker))].sort();
  const filtered = sorted.filter(
    (c) =>
      (company === "All companies" || c.ticker === company) &&
      `${c.company} ${c.ticker} ${c.quarter}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  const measured = sorted.filter((c) => c.citation_accuracy !== null);
  const meanMatch = measured.length
    ? measured.reduce((sum, c) => sum + (c.citation_accuracy ?? 0), 0) /
      measured.length
    : null;
  const latest = sorted[0];
  return (
    <div className="container page reveal">
      <p className="eyebrow muted">The research desk</p>
      <h1 className="page-title">Earnings, in perspective.</h1>
      <p className="page-description">
        Explore the calls. Read the signals. Go straight to the source.
      </p>
      {error ? (
        <ErrorState message={error} />
      ) : !calls ? (
        <LoadingState label="Opening the research library…" />
      ) : calls.length === 0 ? (
        <EmptyState
          title="The library is waiting."
          description="Processed earnings-call reports will appear here when available."
        />
      ) : (
        <>
          <div className="metric-row">
            <div className="metric">
              <div className="metric-value">
                {calls.length.toString().padStart(2, "0")}
              </div>
              <p className="metric-label">Calls in the library</p>
            </div>
            <div className="metric">
              <div className="metric-value">
                {companies.length.toString().padStart(2, "0")}
              </div>
              <p className="metric-label">Companies covered</p>
            </div>
            <div className="metric">
              <div className="metric-value">{formatPercent(meanMatch)}</div>
              <p className="metric-label">
                Mean citation-match rate · {measured.length} calls
              </p>
            </div>
          </div>
          {latest && (
            <section
              className="dark dashboard-lead"
              aria-labelledby="latest-heading"
            >
              <div>
                <p className="eyebrow text-brass">Latest in the library</p>
                <h2 id="latest-heading" className="editorial">
                  {latest.company}
                  <br />
                  {latest.quarter.replace("-", " ")} earnings brief
                </h2>
                <p className="caption mt-4">
                  {formatDate(latest.call_date)}{" "}
                  <span aria-hidden="true"> / </span> {latest.ticker}
                </p>
              </div>
              <div className="lead-summary">
                <p>{latest.overall_summary}</p>
                <Link
                  to={`/app/calls/${latest.ticker}/${latest.quarter}`}
                  className="text-link mt-5"
                >
                  Open the analysis{" "}
                  <ArrowUpRight size={15} aria-hidden="true" />
                </Link>
              </div>
            </section>
          )}
          <section className="section-space" aria-labelledby="reports-heading">
            <div className="section-top">
              <div>
                <p className="eyebrow muted mb-2">The archive</p>
                <h2 className="section-heading" id="reports-heading">
                  Research library
                </h2>
              </div>
              <span className="caption muted tabular" role="status">
                {filtered.length} of {calls.length} reports
              </span>
            </div>
            <div className="toolbar">
              <div className="filters" aria-label="Filter by company">
                {["All companies", ...companies].map((t) => (
                  <button
                    key={t}
                    className="filter-btn"
                    aria-pressed={company === t}
                    onClick={() => setCompany(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <label className="search-field">
                <Search size={15} aria-hidden="true" />
                <span className="sr-only">Search reports</span>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Company, ticker or quarter"
                  type="search"
                />
              </label>
            </div>
            <div className="report-list-head" aria-hidden="true">
              <span>Company</span>
              <span>Reporting period</span>
              <span>Transcript sentiment</span>
              <span>Citation match</span>
              <span />
            </div>
            {filtered.map((c) => (
              <Link
                key={`${c.ticker}-${c.quarter}`}
                className="report-row"
                to={`/app/calls/${c.ticker}/${c.quarter}`}
                aria-label={`Read ${c.company} ${c.quarter.replace("-", " ")} earnings report`}
              >
                <div className="company-cell">
                  <TickerBadge ticker={c.ticker} />
                  <div>
                    <strong>{c.company}</strong>
                    <small>{c.ticker} / earnings call</small>
                  </div>
                </div>
                <div className="report-date">
                  <strong>{c.quarter.replace("-", " ")}</strong>
                  {formatDate(c.call_date)}
                </div>
                <div className="report-tone">
                  <SentimentBar distribution={c.sentiment_distribution} />
                </div>
                <span className="report-match tabular text-sm">
                  {formatPercent(c.citation_accuracy)}
                </span>
                <ArrowUpRight size={17} aria-hidden="true" />
              </Link>
            ))}
            {filtered.length === 0 && (
              <EmptyState
                title="No reports found."
                description="Try another company or a different search term."
              />
            )}
            <p className="caption muted mt-6">
              Citation matching checks source text and timestamps. It does not
              independently verify the meaning of a claim.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
