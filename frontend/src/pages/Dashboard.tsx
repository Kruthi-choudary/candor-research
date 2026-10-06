import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search, ArrowRight } from "lucide-react";
import { api, type CallSummary } from "../lib/api";
import { formatDate } from "../lib/format";
import { TickerBadge } from "../components/TickerBadge";
import { SentimentBar } from "../components/SentimentBar";

export function Dashboard() {
  const [calls, setCalls] = useState<CallSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api
      .listCalls()
      .then((d) => setCalls(d.calls))
      .catch((e) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    if (!calls) return [];
    const q = query.trim().toLowerCase();
    if (!q) return calls;
    return calls.filter(
      (c) => c.ticker.toLowerCase().includes(q) || c.company.toLowerCase().includes(q),
    );
  }, [calls, query]);

  const featured = useMemo(() => {
    if (!calls || calls.length === 0) return undefined;
    return [...calls].sort((a, b) => (b.call_date ?? "").localeCompare(a.call_date ?? ""))[0];
  }, [calls]);

  return (
    <div className="mx-auto max-w-6xl px-10 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-medium text-text">Candor</h1>
          <p className="mt-1 text-sm text-text-muted">
            Turn earnings calls into clear, verified insights.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-border bg-raised px-3 py-2 text-sm text-text-muted">
          <Search size={14} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search companies or reports..."
            className="w-56 bg-transparent outline-none placeholder:text-text-faint"
          />
        </div>
      </div>

      {error && (
        <p className="mt-8 rounded-lg border border-negative/30 bg-negative/10 px-4 py-3 text-sm text-negative">
          {error} — is the API running on :8321?
        </p>
      )}

      {featured && (
        <Link
          to={`/app/calls/${featured.ticker}/${featured.quarter}`}
          className="mt-8 flex items-center justify-between rounded-2xl border border-border bg-raised px-7 py-6 transition-colors hover:border-mint/30"
        >
          <div className="flex items-center gap-4">
            <TickerBadge ticker={featured.ticker} size={48} />
            <div>
              <div className="text-xs uppercase tracking-wide text-text-faint">
                Latest earnings call
              </div>
              <div className="mt-1 text-lg font-medium text-text">
                {featured.company} {featured.quarter.replace("-", " ")} Earnings Call
              </div>
              <div className="text-sm text-text-muted">{formatDate(featured.call_date)}</div>
            </div>
          </div>
          <ArrowRight className="text-text-faint" size={20} />
        </Link>
      )}

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((call) => (
          <Link
            key={`${call.ticker}-${call.quarter}`}
            to={`/app/calls/${call.ticker}/${call.quarter}`}
            className="flex flex-col gap-4 rounded-xl border border-border bg-raised p-5 transition-colors hover:border-mint/30"
          >
            <div className="flex items-center gap-3">
              <TickerBadge ticker={call.ticker} />
              <div>
                <div className="text-sm font-medium text-text">{call.company}</div>
                <div className="text-xs text-text-faint">
                  {call.quarter.replace("-", " ")} · {formatDate(call.call_date)}
                </div>
              </div>
            </div>
            <p className="line-clamp-2 text-xs text-text-muted">{call.overall_summary}</p>
            <SentimentBar distribution={call.sentiment_distribution} />
          </Link>
        ))}
      </div>

      {calls && filtered.length === 0 && (
        <p className="mt-10 text-center text-sm text-text-faint">No calls match "{query}".</p>
      )}
    </div>
  );
}
