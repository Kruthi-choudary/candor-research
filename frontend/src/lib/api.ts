import {
  isCalls,
  isCompanies,
  isReport,
  isClaims,
  isTranscript,
  isEvaluation,
} from "./api-validation.ts";
// Local dev: Vite proxies "/api" to the local FastAPI server (see vite.config.ts).
// Production build: set VITE_API_BASE_URL to the deployed API's full URL (e.g. a Render
// service) at build time -- see README "Deploying".
const BASE = import.meta.env?.VITE_API_BASE_URL ?? "/api";

export interface Company {
  ticker: string;
  name: string;
}

export interface SentimentDistribution {
  positive: number;
  negative: number;
  neutral: number;
}

export interface CallSummary {
  ticker: string;
  quarter: string; // "Q1-2025" (URL-safe)
  company: string;
  call_date: string | null;
  overall_summary: string;
  sentiment_distribution: SentimentDistribution;
  citation_accuracy: number | null;
}

export interface CitationVerification {
  total_citations: number;
  verified: number;
  accuracy: number | null;
}

export interface PriorQuarterContext {
  quarter: string;
  start_sec: number;
  text: string;
}

export interface KeyClaim {
  claim: string;
  evidence: string;
  timestamp_sec: number;
  sentiment: "positive" | "negative" | "neutral";
  verdict?: "VERIFIED" | "TEXT_MISMATCH" | "TIMESTAMP_NOT_FOUND" | null;
  match_ratio?: number | null;
}

export interface CallReport {
  report_version?: string;
  schema_version: string;
  ticker: string;
  company: string;
  quarter: string;
  call_date: string | null;
  overall_summary: string;
  sentiment_distribution: SentimentDistribution;
  key_claims: KeyClaim[];
  risks: string[];
  management_outlook: string[];
  citation_verification: CitationVerification;
  audio_features_summary: {
    mean_pitch_hz: number | null;
    mean_energy: number | null;
    mean_speaking_rate_wps: number | null;
    segments_analyzed: number;
  };
  prior_quarter_context_used: PriorQuarterContext[];
  pipeline_version: string;
  stage_durations_sec: Record<string, number>;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  duration_sec: number;
  language: string;
  segments: TranscriptSegment[];
  full_text: string;
}

export interface EvalRun {
  label: string;
  schema_compliance: number | null;
  citation_accuracy: number | null;
  total_citations: number | null;
}

export interface EvalSummary {
  citation_grounding: {
    baseline: EvalRun | null;
    structured: EvalRun | null;
  };
  claim_coverage: {
    calls_evaluated: number;
    avg_precision: number | null;
    avg_recall: number | null;
    avg_f1: number | null;
    results: Array<{
      ticker: string;
      quarter: string;
      precision: number | null;
      recall: number | null;
      f1: number | null;
    }>;
  } | null;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJSON<T>(
  path: string,
  validate: (value: unknown) => value is T,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed: ${res.status}`,
      res.status,
    );
  }
  const value: unknown = await res.json();
  if (!validate(value))
    throw new Error("The analysis service returned an invalid response.");
  return value;
}

const callPath = (ticker: string, quarter: string) =>
  `/calls/${encodeURIComponent(ticker)}/${encodeURIComponent(quarter)}`;
const sameCall = (
  actual: { ticker: string; quarter: string },
  ticker: string,
  quarter: string,
) =>
  actual.ticker === ticker.toUpperCase() &&
  actual.quarter.replace(/[ _]/g, "-") === quarter.replace(/[ _]/g, "-");

export const api = {
  listCompanies: (signal?: AbortSignal) =>
    getJSON("/companies", isCompanies, signal),
  listCalls: (signal?: AbortSignal) => getJSON("/calls", isCalls, signal),
  getCall: async (ticker: string, quarter: string, signal?: AbortSignal) => {
    const report = await getJSON(callPath(ticker, quarter), isReport, signal);
    if (!sameCall(report, ticker, quarter))
      throw new Error("The report belongs to a different call.");
    return report;
  },
  getClaims: async (ticker: string, quarter: string, signal?: AbortSignal) => {
    const claims = await getJSON(
      `${callPath(ticker, quarter)}/claims`,
      isClaims,
      signal,
    );
    if (!sameCall(claims, ticker, quarter))
      throw new Error("The claims belong to a different call.");
    return claims;
  },
  getTranscript: (ticker: string, quarter: string, signal?: AbortSignal) =>
    getJSON(`${callPath(ticker, quarter)}/transcript`, isTranscript, signal),
  audioUrl: (ticker: string, quarter: string) =>
    `${BASE}${callPath(ticker, quarter)}/audio`,
  getEvalSummary: (signal?: AbortSignal) =>
    getJSON("/eval/summary", isEvaluation, signal),
  analyze: async (ticker: string, quarter: string) => {
    const res = await fetch(
      `${BASE}/analyze?ticker=${ticker}&quarter=${quarter}`,
      { method: "POST" },
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail ?? `Request failed: ${res.status}`);
    }
    return res.json() as Promise<CallReport>;
  },
};
