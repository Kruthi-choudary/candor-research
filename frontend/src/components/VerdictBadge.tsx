import { Check, AlertTriangle, HelpCircle } from "lucide-react";

export function VerdictBadge({ verdict }: { verdict?: string | null }) {
  const verified = verdict === "VERIFIED";
  const unchecked = !verdict;
  const Icon = verified ? Check : unchecked ? HelpCircle : AlertTriangle;
  const label = verified
    ? "Citation matched"
    : unchecked
      ? "Not checked"
      : verdict === "TIMESTAMP_NOT_FOUND"
        ? "Timestamp not found"
        : "Citation mismatch";
  return (
    <span
      className={`badge ${unchecked ? "badge-unchecked" : verified ? "" : "badge-warning"}`}
      title={
        verified
          ? "Quote text matched near the cited timestamp. Claim meaning has not been independently verified."
          : undefined
      }
    >
      <Icon size={12} aria-hidden="true" />
      {label}
    </span>
  );
}
