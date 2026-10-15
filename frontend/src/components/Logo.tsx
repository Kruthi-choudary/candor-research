export function Logo({ size = "md" }: { size?: "sm" | "md" }) {
  return (
    <span className={`wordmark ${size === "sm" ? "wordmark-small" : ""}`}>
      <svg
        className="brand-symbol"
        viewBox="0 0 24 28"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M18 3H8L3 14l5 11h10M7 14h14M12 8v12"
          stroke="currentColor"
          strokeWidth="1.4"
        />
      </svg>
      CANDOR
    </span>
  );
}
