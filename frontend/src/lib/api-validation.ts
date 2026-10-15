// Runtime checks protect the demo-to-live boundary: a 200 response alone is not data.
import type {
  CallReport,
  CallSummary,
  Company,
  EvalSummary,
  KeyClaim,
  Transcript,
} from "./api";
type RecordValue = Record<string, unknown>;
const record = (v: unknown): v is RecordValue =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string";
const finite = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);
const count = (v: unknown): v is number =>
  finite(v) && v >= 0 && Number.isInteger(v);
const nullableNumber = (v: unknown) => v === null || finite(v);
const score = (v: unknown) => v === null || (finite(v) && v >= 0 && v <= 1);
const strings = (v: unknown) => Array.isArray(v) && v.every(text);
const distribution = (v: unknown) =>
  record(v) &&
  ["positive", "negative", "neutral"].every(
    (k) => finite(v[k]) && (v[k] as number) >= 0 && (v[k] as number) <= 100,
  );
const quarter = (v: unknown) => text(v) && /^Q[1-4][ _-]\d{4}$/.test(v);
const callIdentity = (v: RecordValue) =>
  text(v.ticker) && v.ticker.length > 0 && quarter(v.quarter);
const date = (v: unknown) =>
  v === null ||
  (text(v) && /^\d{4}-\d{2}-\d{2}$/.test(v) && Number.isFinite(Date.parse(v)));
export const isClaim = (v: unknown): v is KeyClaim =>
  record(v) &&
  text(v.claim) &&
  text(v.evidence) &&
  finite(v.timestamp_sec) &&
  v.timestamp_sec >= 0 &&
  ["positive", "negative", "neutral"].includes(v.sentiment as string) &&
  (v.verdict == null ||
    ["VERIFIED", "TEXT_MISMATCH", "TIMESTAMP_NOT_FOUND"].includes(
      v.verdict as string,
    )) &&
  (v.match_ratio === undefined || score(v.match_ratio));
export const isCalls = (v: unknown): v is { calls: CallSummary[] } =>
  record(v) &&
  Array.isArray(v.calls) &&
  v.calls.every(
    (c) =>
      record(c) &&
      callIdentity(c) &&
      text(c.company) &&
      date(c.call_date) &&
      text(c.overall_summary) &&
      distribution(c.sentiment_distribution) &&
      score(c.citation_accuracy),
  );
export const isCompanies = (v: unknown): v is { companies: Company[] } =>
  record(v) &&
  Array.isArray(v.companies) &&
  v.companies.every((c) => record(c) && text(c.ticker) && text(c.name));
export const isClaims = (
  v: unknown,
): v is { ticker: string; quarter: string; claims: KeyClaim[] } =>
  record(v) &&
  callIdentity(v) &&
  Array.isArray(v.claims) &&
  v.claims.every(isClaim);
export const isReport = (v: unknown): v is CallReport => {
  if (
    !record(v) ||
    !callIdentity(v) ||
    !text(v.company) ||
    !date(v.call_date) ||
    !text(v.overall_summary) ||
    !text(v.schema_version) ||
    !text(v.pipeline_version)
  )
    return false;
  if (
    !distribution(v.sentiment_distribution) ||
    !Array.isArray(v.key_claims) ||
    !v.key_claims.every(isClaim) ||
    !strings(v.risks) ||
    !strings(v.management_outlook)
  )
    return false;
  const citation = v.citation_verification,
    audio = v.audio_features_summary;
  if (
    !record(citation) ||
    !count(citation.total_citations) ||
    !count(citation.verified) ||
    citation.verified > citation.total_citations ||
    !score(citation.accuracy)
  )
    return false;
  if (
    !record(audio) ||
    !count(audio.segments_analyzed) ||
    !["mean_pitch_hz", "mean_energy", "mean_speaking_rate_wps"].every((k) =>
      nullableNumber(audio[k]),
    )
  )
    return false;
  return (
    Array.isArray(v.prior_quarter_context_used) &&
    v.prior_quarter_context_used.every(
      (c) =>
        record(c) && quarter(c.quarter) && finite(c.start_sec) && text(c.text),
    ) &&
    record(v.stage_durations_sec) &&
    Object.values(v.stage_durations_sec).every((n) => finite(n) && n >= 0)
  );
};
export const isTranscript = (v: unknown): v is Transcript =>
  record(v) &&
  finite(v.duration_sec) &&
  v.duration_sec >= 0 &&
  text(v.language) &&
  text(v.full_text) &&
  Array.isArray(v.segments) &&
  v.segments.every(
    (s) =>
      record(s) &&
      finite(s.start) &&
      finite(s.end) &&
      s.start >= 0 &&
      s.end >= s.start &&
      text(s.text),
  );
export const isEvaluation = (v: unknown): v is EvalSummary => {
  if (!record(v) || !record(v.citation_grounding)) return false;
  const run = (r: unknown) =>
    r === null ||
    (record(r) &&
      text(r.label) &&
      score(r.schema_compliance) &&
      score(r.citation_accuracy) &&
      count(r.total_citations));
  if (
    !run(v.citation_grounding.baseline) ||
    !run(v.citation_grounding.structured)
  )
    return false;
  const c = v.claim_coverage;
  return (
    c === null ||
    (record(c) &&
      count(c.calls_evaluated) &&
      score(c.avg_precision) &&
      score(c.avg_recall) &&
      score(c.avg_f1) &&
      Array.isArray(c.results) &&
      c.results.every(
        (r) =>
          record(r) &&
          callIdentity(r) &&
          score(r.precision) &&
          score(r.recall) &&
          score(r.f1),
      ))
  );
};
