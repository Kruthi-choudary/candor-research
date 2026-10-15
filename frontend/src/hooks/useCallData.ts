import { resources, useAnalysisResource } from "./useAnalysis";

export function useCallData(ticker: string, quarter: string) {
  const report = useAnalysisResource(resources.report(ticker, quarter));
  const claims = useAnalysisResource(resources.claims(ticker, quarter));
  const transcript = useAnalysisResource(resources.transcript(ticker, quarter));
  return {
    reportResource: report,
    sources: {
      report: report.source,
      claims: claims.source,
      [transcript.source === "demo" ? "transcript excerpts" : "transcript"]:
        transcript.source,
    },
    reportIsLive: report.source === "live",
    claimsAreLive: claims.source === "live",
    transcriptIsLive: transcript.source === "live",
    data: report.data
      ? {
          report: report.data,
          claims: claims.data?.claims ?? report.data.key_claims,
          transcript: transcript.data,
          claimsError: null,
          transcriptError:
            transcript.data || !transcript.error
              ? null
              : "The full transcript is temporarily unavailable. Claim evidence remains available above.",
        }
      : null,
  };
}
