// Build the offline preview from existing project outputs, never from invented metrics.
// Run: node frontend/scripts/build-demo.mjs (from the repository root).
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
const { values: options } = parseArgs({ options: {
  "override-bundle": { type: "string" }, output: { type: "string" },
} });
const override = options["override-bundle"]
  ? JSON.parse(readFileSync(options["override-bundle"], "utf8")) : null;
const root = fileURLToPath(new URL("../../", import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(root, path), "utf8"));
const calls = [];
const reports = {};
const claims = {};
const transcripts = {};
for (const ticker of ["AAPL", "MSFT", "NVDA", "META"]) {
  const quarter = "Q1_2025";
  const key = `${ticker}/Q1-2025`;
  const replacing = override?.report.ticker === ticker && override.report.quarter.replaceAll(" ", "_") === quarter;
  const report = replacing ? override.report : read(`data/processed/pipeline_runs/${ticker}/${quarter}.json`);
  const generated = replacing ? override.structured_claims : read(
    `data/processed/reports_structured_citations_v1/${ticker}/${quarter}.json`,
  );
  const verdicts = (replacing ? override.citation_evaluation : read(
    `data/processed/eval/per_call/${ticker}/${quarter}.json`,
  )).citations;
  const transcript = read(
    `data/processed/transcripts/${ticker}/${quarter}.json`,
  );
  reports[key] = report;
  claims[key] = {
    ticker,
    quarter: report.quarter,
    claims: generated.claims.map((c, i) => ({
      claim: c.claim,
      evidence: c.citation.source_text,
      timestamp_sec: c.citation.timestamp_sec,
      sentiment: c.sentiment,
      verdict: verdicts[i]?.verdict ?? null,
      match_ratio: verdicts[i]?.match_ratio ?? null,
    })),
  };
  // Keep surrounding passages for each claim, not the full hour-long transcript.
  const selected = new Set();
  for (const c of claims[key].claims) {
    let i = transcript.segments.reduce(
      (best, s, index, segments) =>
        Math.abs(s.start - c.timestamp_sec) <
        Math.abs(segments[best].start - c.timestamp_sec)
          ? index
          : best,
      0,
    );
    let end = i;
    // Include the entire cited span, even when a complete passage exceeds three
    // segments. Integer timestamps are copied by truncation, not nearest start.
    let found = false;
    for (let start = 0; start < transcript.segments.length && !found; start++) {
      if (Math.trunc(transcript.segments[start].start) !== c.timestamp_sec) continue;
      let text = "";
      for (let last = start; last < transcript.segments.length; last++) {
        text += `${text ? " " : ""}${transcript.segments[last].text.trim()}`;
        if (text === c.evidence.trim()) {
          i = start; end = last; found = true; break;
        }
        if (!c.evidence.trim().startsWith(text)) break;
      }
    }
    if (report.evidence_policy === "complete_passages_v1" && !found)
      throw new Error(`Complete evidence is missing from the transcript: ${key} at ${c.timestamp_sec}`);
    for (
      let j = Math.max(0, i - 1);
      j < Math.min(transcript.segments.length, end + 3);
      j++
    )
      selected.add(j);
  }
  const segments = [...selected]
    .sort((a, b) => a - b)
    .map((i) => transcript.segments[i]);
  transcripts[key] = {
    duration_sec: transcript.duration_sec,
    language: transcript.language,
    segments,
    full_text: segments.map((s) => s.text).join(" "),
  };
  calls.push({
    ticker,
    quarter: "Q1-2025",
    company: report.company,
    call_date: report.call_date,
    overall_summary: report.overall_summary,
    sentiment_distribution: report.sentiment_distribution,
    citation_accuracy: report.citation_verification.accuracy,
  });
}
const baseline = read(
  "data/processed/eval/citation_accuracy_baseline_free_text_v1.json",
);
const structured = read(
  "data/processed/eval/citation_accuracy_structured_citations_v1.json",
);
const evaluation = {
  citation_grounding: {
    baseline: {
      label: "Archived free-text citations",
      schema_compliance: baseline.format_compliance,
      citation_accuracy: baseline.overall_accuracy,
      total_citations: baseline.total_citations,
    },
    structured: {
      label: "Archived JSON-schema citations",
      schema_compliance: structured.format_compliance,
      citation_accuracy: structured.overall_accuracy,
      total_citations: structured.total_citations,
    },
  },
  claim_coverage: read("data/processed/eval/claim_coverage.json"),
};
const snapshot = {
  provenance:
    "Curated copies of committed Candor outputs; transcript excerpts only; no bundled audio.",
  companies: calls.map(({ ticker, company }) => ({ ticker, name: company })),
  calls,
  reports,
  claims,
  transcripts,
  evaluation,
};
const output = options.output ? resolve(options.output) : join(root, "frontend/src/data/demo.json");
writeFileSync(output, JSON.stringify(snapshot) + "\n");
console.log(
  `Bundled ${calls.length} reports and ${Object.values(transcripts).reduce((n, t) => n + t.segments.length, 0)} transcript excerpts (${Math.round(Buffer.byteLength(JSON.stringify(snapshot)) / 1024)} KB uncompressed).`,
);
