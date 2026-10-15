import { createContext, useContext, useSyncExternalStore } from "react";
import { api } from "../lib/api";
import {
  AnalysisClient,
  type ResourceDefinition,
} from "../lib/analysis-client";
import { demo, callKey } from "../data/demo";

export const AnalysisContext = createContext<AnalysisClient | null>(null);
function useClient() {
  const client = useContext(AnalysisContext);
  if (!client) throw new Error("AnalysisProvider is missing.");
  return client;
}
export function useConnection() {
  const client = useClient();
  return {
    state: useSyncExternalStore(
      client.subscribeConnection,
      client.getConnection,
      client.getConnection,
    ),
    retry: client.retry,
  };
}
export function useAnalysisResource<T>(definition: ResourceDefinition<T>) {
  const handle = useClient().resource(definition);
  return useSyncExternalStore(
    handle.subscribe,
    handle.getSnapshot,
    handle.getSnapshot,
  );
}
export const resources = {
  calls: { key: "calls", demo: { calls: demo.calls }, load: api.listCalls },
  evaluation: {
    key: "evaluation",
    demo: demo.evaluation,
    load: api.getEvalSummary,
  },
  report: (ticker: string, quarter: string) => ({
    key: `report:${callKey(ticker, quarter)}`,
    demo: demo.reports[callKey(ticker, quarter)] ?? null,
    load: (signal: AbortSignal) => api.getCall(ticker, quarter, signal),
  }),
  claims: (ticker: string, quarter: string) => ({
    key: `claims:${callKey(ticker, quarter)}`,
    demo: demo.claims[callKey(ticker, quarter)] ?? null,
    load: (signal: AbortSignal) => api.getClaims(ticker, quarter, signal),
  }),
  transcript: (ticker: string, quarter: string) => ({
    key: `transcript:${callKey(ticker, quarter)}`,
    demo: demo.transcripts[callKey(ticker, quarter)] ?? null,
    load: (signal: AbortSignal) => api.getTranscript(ticker, quarter, signal),
  }),
};
