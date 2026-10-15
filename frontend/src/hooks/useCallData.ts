import { useEffect, useState } from "react";
import {
  api,
  type CallReport,
  type KeyClaim,
  type Transcript,
} from "../lib/api";

interface CallData {
  report: CallReport;
  claims: KeyClaim[] | null;
  transcript: Transcript | null;
  claimsError: string | null;
  transcriptError: string | null;
}

// Call pages are keyed by ticker + quarter in App, so changing calls creates a
// fresh request state while moving between claims preserves the audio instance.
export function useCallData(ticker: string, quarter: string) {
  const [data, setData] = useState<CallData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      api.getCall(ticker, quarter),
      api.getClaims(ticker, quarter),
      api.getTranscript(ticker, quarter),
    ]).then(([report, claims, transcript]) => {
      if (cancelled) return;
      if (report.status === "rejected") {
        setError(
          report.reason instanceof Error
            ? report.reason.message
            : "The report could not be loaded.",
        );
        return;
      }
      setData({
        report: report.value,
        claims: claims.status === "fulfilled" ? claims.value.claims : null,
        transcript: transcript.status === "fulfilled" ? transcript.value : null,
        claimsError:
          claims.status === "rejected"
            ? "The claim evidence could not be loaded. Please reload to try again."
            : null,
        transcriptError:
          transcript.status === "rejected"
            ? "The transcript could not be loaded. Please reload to try again."
            : null,
      });
    });
    return () => {
      cancelled = true;
    };
  }, [ticker, quarter]);
  return { data, error };
}
