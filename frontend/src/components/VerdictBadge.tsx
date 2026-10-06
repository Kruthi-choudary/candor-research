import { Check, AlertTriangle, HelpCircle } from "lucide-react";

const STYLES: Record<string, { label: string; className: string; icon: typeof Check }> = {
  VERIFIED: { label: "Verified", className: "bg-mint/15 text-mint border-mint/30", icon: Check },
  TEXT_MISMATCH: {
    label: "Text mismatch",
    className: "bg-negative/15 text-negative border-negative/30",
    icon: AlertTriangle,
  },
  TIMESTAMP_NOT_FOUND: {
    label: "Timestamp not found",
    className: "bg-negative/15 text-negative border-negative/30",
    icon: AlertTriangle,
  },
};

export function VerdictBadge({ verdict }: { verdict?: string | null }) {
  if (!verdict) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs text-text-faint">
        <HelpCircle size={12} /> Not checked
      </span>
    );
  }
  const style = STYLES[verdict] ?? STYLES.TEXT_MISMATCH;
  const Icon = style.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${style.className}`}>
      <Icon size={12} /> {style.label}
    </span>
  );
}
