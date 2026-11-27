import ErrorBox from "../data/ErrorBox";
import type { ApiError } from "../data/dryadApi";
import type { ModelCard } from "../data/types";

const pct = (x?: number | null) => (x == null ? "n/a" : `${(100 * x).toFixed(0)}%`);
const f3 = (x?: number | null) => (x == null ? "n/a" : x.toFixed(3));

interface Props {
  card: ModelCard | null;
  error: ApiError | null;
  loading: boolean;
  onRetry: () => void;
  onClose: () => void;
}

export default function ModelCardPanel({ card, error, loading, onRetry, onClose }: Props) {
  const oof = card?.evaluation?.whole_blocks_held_out_out_of_fold_2021_2024;
  const sh = card?.evaluation?.shaver_lake_never_seen_deployed_model;
  const table = card?.bands?.table;
  return (
    <aside className="drawer" role="dialog" aria-label="About this score">
      <div className="panel-head">
        <h3>About this score</h3>
        <button onClick={onClose}>Close</button>
      </div>
      {error && <ErrorBox title="Could not load the model card" error={error} onRetry={onRetry} />}
      {loading && !card && <p className="muted">Loading model card...</p>}
      {card && (
        <>
          <p><b>What it predicts.</b> {card.target}</p>
          <p>It estimates where USFS aerial surveys would map tree mortality. It is not a general forest-health measure, and the likelihood is relative to surveyed forest, not a real-world probability. It cannot name a cause.</p>

          <h2>Training data</h2>
          <p>{card.training?.rows?.toLocaleString()} labelled patch-years ({card.training?.positives?.toLocaleString()} damaged), {card.training?.years}, {card.training?.spatial_blocks_20km} map blocks of 20 km. Shaver Lake was never used in training.</p>

          <h2>Tested on data it had not seen</h2>
          <table className="t">
            <thead><tr><th>Test</th><th>AUC</th><th>Top 10% flagged: damaged</th><th>Overall damaged</th></tr></thead>
            <tbody>
              <tr><td>Whole 20 km blocks held out</td><td>{f3(oof?.auc)} ({f3(oof?.auc_95ci?.[0])} to {f3(oof?.auc_95ci?.[1])})</td><td>{pct(oof?.precision_top10pct)}</td><td>{pct(oof?.base_rate)}</td></tr>
              <tr><td>Shaver Lake, never seen ({sh?.positives} damaged of {sh?.n})</td><td>{f3(sh?.auc)}</td><td>{pct(sh?.precision_top10pct)}</td><td>{pct(sh?.base_rate)}</td></tr>
            </tbody>
          </table>
          <p className="muted">AUC is a ranking score: 0.5 is a coin flip and 1.0 is perfect. It is not the percentage of correct answers.</p>

          <h2>Bands (Sierra-wide cutoffs)</h2>
          <table className="t">
            <thead><tr><th>Band</th><th>Share of patches</th><th>Observed damage rate</th></tr></thead>
            <tbody>
              {table && ["High", "Elevated", "Lower"].map((b) => (
                <tr key={b}><td>{b}</td><td>{pct(table[b]?.share_of_cells)}</td><td>{pct(table[b]?.observed_damage_rate)}</td></tr>
              ))}
            </tbody>
          </table>

          <h2>What the model relies on</h2>
          <ul>
            {(card.permutation_importance ?? []).slice(0, 5).map((r: { feature: string }) => (
              <li key={r.feature}>{card.feature_notes?.[r.feature] ?? r.feature}</li>
            ))}
          </ul>

          <h2>Limitations</h2>
          <ul>{(card.limitations ?? []).map((t: string, i: number) => <li key={i}>{t}</li>)}</ul>
          <p className="muted">Research prototype. Model {card.model_version}, built {card.generated_at}.</p>
        </>
      )}
    </aside>
  );
}