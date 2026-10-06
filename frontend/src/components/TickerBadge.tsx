import { tickerColor } from "../lib/format";

export function TickerBadge({ ticker, size = 40 }: { ticker: string; size?: number }) {
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-xl font-semibold"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.32,
        background: `${tickerColor(ticker)}1a`,
        color: tickerColor(ticker),
        border: `1px solid ${tickerColor(ticker)}33`,
      }}
    >
      {ticker.slice(0, 2)}
    </div>
  );
}
