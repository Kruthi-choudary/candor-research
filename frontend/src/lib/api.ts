const BASE = "/api";

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

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  listCompanies: () => getJSON<{ companies: Company[] }>("/companies"),
  listCalls: () => getJSON<{ calls: CallSummary[] }>("/calls"),
  getCall: (ticker: string, quarter: string) =>
    getJSON<CallReport>(`/calls/${ticker}/${quarter}`),
  getClaims: (ticker: string, quarter: string) =>
    getJSON<{ ticker: string; quarter: string; claims: KeyClaim[] }>(
      `/calls/${ticker}/${quarter}/claims`,
    ),
  getTranscript: (ticker: string, quarter: string) =>
    getJSON<Transcript>(`/calls/${ticker}/${quarter}/transcript`),
  audioUrl: (ticker: string, quarter: string) =>
    `${BASE}/calls/${ticker}/${quarter}/audio`,
  getEvalSummary: () => getJSON<EvalSummary>("/eval/summary"),
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
