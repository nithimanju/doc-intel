import { useEffect, useState } from "react";
import type { LocationContext } from "../../shared/types.ts";

interface Props {
  contexts: LocationContext[];
}

export function PdfPane({ contexts }: Props) {
  const [locIdx, setLocIdx] = useState(0);

  useEffect(() => setLocIdx(0), [contexts]);

  if (contexts.length === 0) {
    return (
      <div className="d-flex flex-column align-items-center justify-content-center h-100 text-center text-body-secondary p-5 gap-1">
        <p className="mb-0 fw-semibold">No source location.</p>
        <p className="mb-0 small">
          This candidate is unanswerable by construction (out-of-scope source) — there is
          nothing to open and check.
        </p>
      </div>
    );
  }

  const safeIdx = Math.min(locIdx, contexts.length - 1);
  const loc = contexts[safeIdx];
  const src = `/pdfs/${encodeURIComponent(loc.doc_id)}#page=${loc.page}`;

  return (
    <div className="d-flex flex-column h-100">
      <div className="d-flex align-items-center flex-wrap gap-2 p-2 border-bottom small text-body-secondary">
        {contexts.length > 1 && (
          <div className="btn-group btn-group-sm" role="group" aria-label="Source location">
            {contexts.map((c, i) => (
              <button
                key={i}
                type="button"
                className={`btn ${i === safeIdx ? "btn-primary" : "btn-outline-secondary"}`}
                onClick={() => setLocIdx(i)}
              >
                Loc {i + 1} · p.{c.page}
              </button>
            ))}
          </div>
        )}
        <span className="font-monospace">
          {loc.doc_id} · page {loc.page}
          {loc.region ? ` · ${loc.region}` : ""}
        </span>
      </div>
      <iframe key={src} title="Source PDF" src={src} className="flex-grow-1 border-0 w-100" />
    </div>
  );
}
