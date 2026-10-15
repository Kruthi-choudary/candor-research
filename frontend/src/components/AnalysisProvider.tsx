import { useEffect, useState, type ReactNode } from "react";
import { AnalysisContext } from "../hooks/useAnalysis";
import { AnalysisClient } from "../lib/analysis-client";
import { api } from "../lib/api";

export function AnalysisProvider({
  children,
  client: supplied,
}: {
  children: ReactNode;
  client?: AnalysisClient;
}) {
  // /companies is a small existing endpoint; the API client validates its body.
  const [client] = useState(
    () => supplied ?? new AnalysisClient((signal) => api.listCompanies(signal)),
  );
  useEffect(() => {
    client.start();
    return () => client.stop();
  }, [client]);
  return (
    <AnalysisContext.Provider value={client}>
      {children}
    </AnalysisContext.Provider>
  );
}
