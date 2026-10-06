import type { SentimentDistribution } from "../lib/api";

export function SentimentBar({ distribution }: { distribution: SentimentDistribution }) {
  return (
    <div className="w-full">
      <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-raised-2">
        <div className="h-full bg-mint" style={{ width: `${distribution.positive}%` }} />
        <div className="h-full bg-neutral" style={{ width: `${distribution.neutral}%` }} />
        <div className="h-full bg-negative" style={{ width: `${distribution.negative}%` }} />
      </div>
      <div className="mt-1.5 flex gap-3 text-[11px] text-text-faint">
        <span>{distribution.positive.toFixed(0)}% pos</span>
        <span>{distribution.neutral.toFixed(0)}% neu</span>
        <span>{distribution.negative.toFixed(0)}% neg</span>
      </div>
    </div>
  );
}
