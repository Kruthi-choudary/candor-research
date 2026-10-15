export function LoadingState({
  label = "Loading research…",
}: {
  label?: string;
}) {
  return (
    <div className="state-panel" role="status">
      <div className="loading-line" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-panel" role="alert">
      <h2>Research is temporarily unavailable.</h2>
      <p>{message}</p>
      <button
        className="btn btn-outline"
        onClick={() => window.location.reload()}
      >
        Try again
      </button>
    </div>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="state-panel">
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}
