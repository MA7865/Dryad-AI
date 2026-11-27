import type { ApiError } from "./dryadApi";

export default function ErrorBox({ title, error, onRetry }: { title: string; error: ApiError; onRetry?: () => void }) {
  return (
    <div className="errorbox" role="alert">
      <strong>{title}</strong>
      <div>Endpoint: <code>{error.endpoint}</code></div>
      <div>Status: {error.status || "no response"}</div>
      <div>Detail: {error.detail}</div>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}