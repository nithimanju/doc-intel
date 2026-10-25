import type { CandidateWithContext } from "../../shared/types.ts";

export function ProgressBar({ candidates }: { candidates: CandidateWithContext[] }) {
  const total = candidates.length;
  const counts = { accepted: 0, rejected: 0, flagged_hard: 0, pending: 0 };
  for (const c of candidates) counts[c.pass2_status]++;
  const reviewed = total - counts.pending;
  const pct = (n: number) => (total ? (100 * n) / total : 0);

  return (
    <div className="d-flex flex-column gap-1 flex-grow-1 flex-xl-grow-0" style={{ minWidth: "160px", maxWidth: "320px" }}>
      <div className="progress" role="progressbar" aria-label="Review progress" style={{ height: "6px" }}>
        <div className="progress-bar bg-success" style={{ width: `${pct(counts.accepted)}%` }} />
        <div className="progress-bar bg-danger" style={{ width: `${pct(counts.rejected)}%` }} />
        <div className="progress-bar bg-warning" style={{ width: `${pct(counts.flagged_hard)}%` }} />
      </div>
      <div className="d-flex flex-wrap gap-2 gap-xl-3 small font-monospace" style={{ fontVariantNumeric: "tabular-nums" }}>
        <span>
          <strong>{reviewed}</strong>/{total} reviewed
        </span>
        <span className="text-success">{counts.accepted} accepted</span>
        <span className="text-danger">{counts.rejected} rejected</span>
        <span className="text-warning-emphasis">{counts.flagged_hard} flagged</span>
      </div>
    </div>
  );
}
