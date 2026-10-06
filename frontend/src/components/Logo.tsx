export function Logo({ size = "md" }: { size?: "sm" | "md" }) {
  const text = size === "sm" ? "text-sm" : "text-base";
  return (
    <div className="flex items-center gap-2">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M9 3 L3 21" stroke="#3ecf8e" strokeWidth="3" strokeLinecap="round" />
        <path d="M15 3 L9 21" stroke="#3ecf8e" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <span className={`${text} font-semibold tracking-tight text-text`}>Candor</span>
    </div>
  );
}
