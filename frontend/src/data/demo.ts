import snapshot from "./demo.json";
import type {
  CallReport,
  CallSummary,
  Company,
  EvalSummary,
  KeyClaim,
  Transcript,
} from "../lib/api";

// Frozen project outputs, separate from all live API responses. No audio is bundled.
export const demo = snapshot as {
  provenance: string;
  companies: Company[];
  calls: CallSummary[];
  reports: Record<string, CallReport>;
  claims: Record<
    string,
    { ticker: string; quarter: string; claims: KeyClaim[] }
  >;
  transcripts: Record<string, Transcript>;
  evaluation: EvalSummary;
};
export const callKey = (ticker: string, quarter: string) =>
  `${ticker.toUpperCase()}/${quarter.replace(/[ _]/g, "-")}`;
