import { Link } from "react-router-dom";
import { useConnection } from "../hooks/useAnalysis";
import type { DataSource, ResourceSnapshot } from "../lib/analysis-client";
import { demo } from "../data/demo";

export function ConnectionStatus() {
  const { state, retry } = useConnection();
  const label =
    state === "connecting"
      ? "Connecting to live analysis…"
      : state === "live"
        ? "Live data"
        : "Interactive demo";
  return (
    <div className="connection-bar">
      <div className="container connection-inner">
        <span
          className={`connection-label connection-${state}`}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <span className="connection-dot" aria-hidden="true" />
          {label}
        </span>
        <span className="connection-explanation">
          {state === "live"
            ? "Backend connected · each section identifies its data source"
            : "Bundled examples work independently of the live service"}
        </span>
        {state === "demo" && (
          <button className="connection-retry" onClick={retry}>
            Retry connection
          </button>
        )}
      </div>
    </div>
  );
}

export function DataSourceNote({
  sources,
}: {
  sources: Record<string, DataSource>;
}) {
  const { state } = useConnection();
  const preview = Object.entries(sources)
    .filter(([, source]) => source === "demo")
    .map(([label]) => label);
  const live = Object.entries(sources)
    .filter(([, source]) => source === "live")
    .map(([label]) => label);
  return (
    <div className="data-source-note" aria-live="polite" aria-atomic="true">
      <span className={`source-tag ${preview.length ? "source-demo" : ""}`}>
        {preview.length
          ? "Bundled demo"
          : live.length
            ? state === "live"
              ? "Live API"
              : "Saved live data"
            : "Preview available"}
      </span>
      <span>
        {preview.length
          ? `Demonstration snapshot: ${preview.join(", ")}. ${live.length ? `Live API: ${live.join(", ")}.` : "Not a live result; updates automatically when valid live data arrives."}`
          : live.length
            ? state === "live"
              ? "Showing validated responses from the connected API."
              : "Showing previously loaded live responses while the service reconnects."
            : "This call is not bundled. Explore a sample while the live service connects."}
      </span>
    </div>
  );
}

export function CallPreviewUnavailable({
  ticker,
  quarter,
  resource,
}: {
  ticker: string;
  quarter: string;
  resource: ResourceSnapshot<unknown>;
}) {
  const sample =
    demo.calls.find((c) => c.ticker === ticker.toUpperCase()) ?? demo.calls[0]!;
  return (
    <div className="container page">
      <p className="eyebrow muted">
        {ticker} / {quarter.replace(/[ _-]/g, " ")}
      </p>
      <h1 className="page-title">Explore an earnings conversation.</h1>
      <DataSourceNote sources={{ report: resource.source }} />
      <p className="page-description">
        {resource.error
          ? "This report is currently unavailable from the live service."
          : "This report will open automatically when its live response arrives."}{" "}
        The interactive preview includes four sample calls, with claims and
        transcript excerpts you can inspect now.
      </p>
      <article className="demo-alternative">
        <p className="eyebrow muted">Available bundled example</p>
        <h2 className="section-heading mt-3">
          {sample.company} · {sample.quarter.replace("-", " ")}
        </h2>
        <p className="muted mt-4">{sample.overall_summary}</p>
        <Link
          className="btn mt-6"
          to={`/app/calls/${sample.ticker}/${sample.quarter}`}
        >
          Explore this sample
        </Link>
        <Link className="text-link ml-5" to="/app">
          Research library
        </Link>
      </article>
    </div>
  );
}
