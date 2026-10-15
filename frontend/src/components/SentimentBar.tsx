import type { SentimentDistribution } from "../lib/api";

export function SentimentBar({
  distribution,
}: {
  distribution: SentimentDistribution;
}) {
  return (
    <div
      aria-label={`Transcript sentiment: ${distribution.positive}% positive, ${distribution.neutral}% neutral, ${distribution.negative}% negative`}
    >
      <div className="sentiment-track" aria-hidden="true">
        <span
          className="sentiment-positive"
          style={{ width: `${distribution.positive}%` }}
        />
        <span
          className="sentiment-neutral"
          style={{ width: `${distribution.neutral}%` }}
        />
        <span
          className="sentiment-negative"
          style={{ width: `${distribution.negative}%` }}
        />
      </div>
      <div className="sentiment-labels tabular" aria-hidden="true">
        <span>
          <i className="legend-dot sentiment-positive" />
          {distribution.positive.toFixed(1)}% positive
        </span>
        <span>
          <i className="legend-dot sentiment-neutral" />
          {distribution.neutral.toFixed(1)}% neutral
        </span>
        <span>
          <i className="legend-dot sentiment-negative" />
          {distribution.negative.toFixed(1)}% negative
        </span>
      </div>
    </div>
  );
}
