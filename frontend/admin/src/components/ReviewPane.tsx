import { useEffect, useState } from "react";
import type { CandidateWithContext, DecisionAction } from "../../shared/types.ts";

interface Props {
  candidate: CandidateWithContext;
  submitting: boolean;
  onDecision: (action: DecisionAction, extra?: { reason?: string; question?: string; answer?: string }) => void;
}

export function ReviewPane({ candidate, submitting, onDecision }: Props) {
  const [editing, setEditing] = useState(false);
  const [draftQ, setDraftQ] = useState(candidate.question);
  const [draftA, setDraftA] = useState(candidate.answer);

  useEffect(() => {
    setEditing(false);
    setDraftQ(candidate.question);
    setDraftA(candidate.answer);
  }, [candidate.idx]);

  const needsReview = candidate.licence === "needs_review-manufacturer_authored_mandatory_disclosure";

  return (
    <div className="d-flex flex-column gap-3 h-100 overflow-y-auto border-end p-3 pb-5">
      <div className="d-flex flex-wrap gap-2">
        <span className="badge rounded-pill text-bg-primary">{candidate.answer_type}</span>
        <span className="badge rounded-pill text-bg-secondary">{candidate.source}</span>
        <span className={`badge rounded-pill ${candidate.confidence === "low" ? "text-bg-danger" : "text-bg-secondary"}`}>
          confidence: {candidate.confidence}
        </span>
        {needsReview && <span className="badge rounded-pill text-bg-warning">licence: needs review</span>}
        {candidate.question_id && (
          <span className="badge rounded-pill text-bg-success font-monospace">{candidate.question_id}</span>
        )}
      </div>

      {editing ? (
        <>
          <div>
            <label className="form-label small text-uppercase text-body-secondary" htmlFor="edit-q">
              Question
            </label>
            <textarea
              id="edit-q"
              className="form-control font-monospace small"
              value={draftQ}
              onChange={(e) => setDraftQ(e.target.value)}
              rows={3}
            />
          </div>
          <div>
            <label className="form-label small text-uppercase text-body-secondary" htmlFor="edit-a">
              Answer
            </label>
            <textarea
              id="edit-a"
              className="form-control font-monospace small"
              value={draftA}
              onChange={(e) => setDraftA(e.target.value)}
              rows={2}
            />
          </div>
        </>
      ) : (
        <>
          <p className="fs-5 fw-semibold mb-0">{candidate.question}</p>
          <div>
            <div className="small text-uppercase text-body-secondary mb-1">Answer</div>
            <code className="d-inline-block bg-body-tertiary border rounded px-2 py-1 fs-6">{candidate.answer}</code>
          </div>
        </>
      )}

      {candidate.evidence_quotes.length > 0 && (
        <div>
          <div className="small text-uppercase text-body-secondary mb-1">
            Evidence quote{candidate.evidence_quotes.length > 1 ? "s" : ""}
          </div>
          {candidate.evidence_quotes.map((q, i) => (
            <blockquote key={i} className="border-start border-primary border-3 ps-3 py-1 mb-2 font-monospace small text-wrap">
              “{q}”
            </blockquote>
          ))}
        </div>
      )}

      {candidate.contexts.length > 0 && (
        <details className="border rounded" open>
          <summary className="p-2 small text-body-secondary bg-body-tertiary rounded-top" style={{ cursor: "pointer" }}>
            Page context (verify against this, or the PDF on the right)
          </summary>
          <div className="p-2 d-flex flex-column gap-2">
            {candidate.contexts.map((ctx, i) => (
              <div key={i} className="card">
                <div className="card-header small text-body-secondary py-1 px-2">
                  {ctx.doc_id} · p.{ctx.page} {ctx.region && `· ${ctx.region}`}
                </div>
                <pre className="card-body font-monospace small mb-0" style={{ maxHeight: "220px", overflowY: "auto", whiteSpace: "pre-wrap" }}>
                  {ctx.excerpt || "(no page text available)"}
                </pre>
              </div>
            ))}
          </div>
        </details>
      )}

      {candidate.notes && <p className="small fst-italic text-body-secondary mb-0">{candidate.notes}</p>}

      <div className="d-flex gap-2 mt-auto sticky-bottom bg-body border rounded p-2 shadow-sm">
        {editing ? (
          <>
            <button type="button" className="btn btn-outline-secondary" onClick={() => setEditing(false)} disabled={submitting}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-success"
              disabled={submitting}
              onClick={() => {
                onDecision("edit", { question: draftQ, answer: draftA });
                setEditing(false);
              }}
            >
              Save edit
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn btn-danger" disabled={submitting} onClick={() => onDecision("reject")}>
              Reject
            </button>
            <button type="button" className="btn btn-success" disabled={submitting} onClick={() => onDecision("accept")}>
              Accept
            </button>
            <button type="button" className="btn btn-outline-secondary" disabled={submitting} onClick={() => setEditing(true)}>
              Edit
            </button>
            <button type="button" className="btn btn-outline-warning" disabled={submitting} onClick={() => onDecision("flag")}>
              Flag hard
            </button>
          </>
        )}
      </div>
    </div>
  );
}
