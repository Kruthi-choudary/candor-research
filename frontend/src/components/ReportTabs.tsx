export type ReportTab = "overview" | "claims" | "transcript";
const TABS: ReportTab[] = ["overview", "claims", "transcript"];

export function ReportTabs({
  selected,
  onSelect,
  count,
}: {
  selected: ReportTab;
  onSelect: (tab: ReportTab) => void;
  count: number;
}) {
  return (
    <div className="tabs" role="tablist" aria-label="Report sections">
      {TABS.map((tab, i) => (
        <button
          key={tab}
          id={`tab-${tab}`}
          role="tab"
          type="button"
          aria-selected={selected === tab}
          aria-controls="report-panel"
          tabIndex={selected === tab ? 0 : -1}
          onClick={() => onSelect(tab)}
          onKeyDown={(event) => {
            let next: number | null = null;
            if (event.key === "ArrowRight") next = (i + 1) % TABS.length;
            if (event.key === "ArrowLeft")
              next = (i + TABS.length - 1) % TABS.length;
            if (event.key === "Home") next = 0;
            if (event.key === "End") next = TABS.length - 1;
            if (next !== null) {
              event.preventDefault();
              onSelect(TABS[next]!);
              document.getElementById(`tab-${TABS[next]}`)?.focus();
            }
          }}
        >
          {tab === "overview"
            ? "The brief"
            : tab === "claims"
              ? `Claims & evidence (${count})`
              : "Transcript"}
        </button>
      ))}
    </div>
  );
}
