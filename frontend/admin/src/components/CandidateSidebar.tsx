import { useMemo, useState } from "react";
import type { AnswerType, CandidateWithContext, Pass2Status } from "../../shared/types.ts";
import { StatusBadge } from "./StatusBadge.tsx";

const TYPE_ORDER: AnswerType[] = ["table_numeric", "multi_hop", "unanswerable", "ambiguous", "single_fact"];

interface Props {
  candidates: CandidateWithContext[];
  selectedIdx: number | null;
  onSelect: (idx: number) => void;
}

export function CandidateSidebar({ candidates, selectedIdx, onSelect }: Props) {
  const [typeFilter, setTypeFilter] = useState<AnswerType | "all">("all");
  const [statusFilter, setStatusFilter] = useState<Pass2Status | "all">("all");

  const ordered = useMemo(() => {
    const byType = new Map<number, number>();
    candidates.forEach((c, i) => byType.set(i, TYPE_ORDER.indexOf(c.answer_type)));
    return candidates
      .map((c, idx) => ({ c, idx }))
      .filter(({ c }) => typeFilter === "all" || c.answer_type === typeFilter)
      .filter(({ c }) => statusFilter === "all" || c.pass2_status === statusFilter)
      .sort((a, b) => byType.get(a.idx)! - byType.get(b.idx)! || a.idx - b.idx);
  }, [candidates, typeFilter, statusFilter]);

  function jumpToNextPending() {
    const next = ordered.find(({ c }) => c.pass2_status === "pending");
    if (next) onSelect(next.idx);
  }

  return (
    <aside className="d-flex flex-column h-100 border-end bg-body">
      <div className="d-flex flex-wrap gap-2 p-2 border-bottom">
        <select
          className="form-select form-select-sm w-auto"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as AnswerType | "all")}
        >
          <option value="all">All types</option>
          {TYPE_ORDER.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          className="form-select form-select-sm w-auto"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as Pass2Status | "all")}
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="flagged_hard">Flagged</option>
        </select>
        <button type="button" className="btn btn-sm btn-outline-primary ms-auto" onClick={jumpToNextPending}>
          Next pending →
        </button>
      </div>
      <div className="list-group list-group-flush overflow-y-auto flex-grow-1">
        {ordered.map(({ c, idx }) => (
          <button
            key={idx}
            type="button"
            className={`list-group-item list-group-item-action d-flex align-items-center gap-2 py-2${
              idx === selectedIdx ? " active" : ""
            }`}
            onClick={() => onSelect(idx)}
          >
            <span className="font-monospace text-body-secondary small" style={{ width: "1.8em" }}>
              {idx}
            </span>
            <span className="text-uppercase text-primary-emphasis small" style={{ width: "5.5em", flexShrink: 0 }}>
              {c.answer_type}
            </span>
            <span className="text-truncate small flex-grow-1 text-start">{c.question}</span>
            <StatusBadge status={c.pass2_status} />
          </button>
        ))}
        {ordered.length === 0 && <div className="p-3 text-body-secondary small">No candidates match these filters.</div>}
      </div>
    </aside>
  );
}
