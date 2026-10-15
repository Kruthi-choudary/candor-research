export function TickerBadge({
  ticker,
  size = 40,
}: {
  ticker: string;
  size?: number;
}) {
  return (
    <span
      className="ticker"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {ticker}
    </span>
  );
}
