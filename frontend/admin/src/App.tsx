import { useEffect, useMemo, useState } from "react";
import type { CandidateWithContext, DecisionAction } from "../shared/types.ts";
import { fetchCandidates, sendDecision } from "./api/client.ts";
import { CandidateSidebar } from "./components/CandidateSidebar.tsx";
import { ReviewPane } from "./components/ReviewPane.tsx";
import { PdfPane } from "./components/PdfPane.tsx";
import { ProgressBar } from "./components/ProgressBar.tsx";

type MobileView = "list" | "review" | "pdf";

export default function App() {
  const [candidates, setCandidates] = useState<CandidateWithContext[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mobileView, setMobileView] = useState<MobileView>("list");

  useEffect(() => {
    fetchCandidates()
      .then((data) => {
        setCandidates(data);
        const firstPending = data.findIndex((c) => c.pass2_status === "pending");
        setSelectedIdx(firstPending === -1 ? (data.length ? 0 : null) : firstPending);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const selected = useMemo(
    () => (candidates && selectedIdx !== null ? candidates[selectedIdx] : null),
    [candidates, selectedIdx],
  );

  function handleSelect(idx: number) {
    setSelectedIdx(idx);
    setMobileView("review");
  }

  async function handleDecision(
    action: DecisionAction,
    extra?: { reason?: string; question?: string; answer?: string },
  ) {
    if (selectedIdx === null || !candidates) return;
    setSubmitting(true);
    try {
      const updated = await sendDecision({ idx: selectedIdx, action, ...extra });
      const next = [...candidates];
      next[selectedIdx] = updated;
      setCandidates(next);
      if (action !== "edit") {
        const nextPending = next.findIndex((c, i) => i !== selectedIdx && c.pass2_status === "pending");
        if (nextPending !== -1) setSelectedIdx(nextPending);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (error) {
    return (
      <div className="container py-5 text-center text-body-secondary">
        <h1 className="h4 text-body">Could not load</h1>
        <p>{error}</p>
        <p className="small">
          Issue with the Eval Data Pipeline.
        </p>
      </div>
    );
  }

  if (!candidates) {
    return <div className="container py-5 text-center text-body-secondary">Loading the candidates…</div>;
  }

  return (
    <div className="d-flex flex-column vh-100">
      <header className="d-flex align-items-center justify-content-between flex-wrap gap-3 px-3 py-2 border-bottom bg-body">
        <h1 className="h6 mb-0">Golden Set — Pass 2 Review</h1>
        <ProgressBar candidates={candidates} />
      </header>
      <div className="d-xl-none d-flex border-bottom bg-body" role="tablist" aria-label="Review panes">
        <button
          type="button"
          role="tab"
          aria-selected={mobileView === "list"}
          className={`btn btn-sm flex-fill rounded-0 ${mobileView === "list" ? "btn-primary" : "btn-light"}`}
          onClick={() => setMobileView("list")}
        >
          List
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobileView === "review"}
          className={`btn btn-sm flex-fill rounded-0 ${mobileView === "review" ? "btn-primary" : "btn-light"}`}
          onClick={() => setMobileView("review")}
          disabled={!selected}
        >
          Review
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobileView === "pdf"}
          className={`btn btn-sm flex-fill rounded-0 ${mobileView === "pdf" ? "btn-primary" : "btn-light"}`}
          onClick={() => setMobileView("pdf")}
          disabled={!selected}
        >
          PDF
        </button>
      </div>

      <div className="review-grid flex-grow-1">
        <div className={`${mobileView === "list" ? "d-flex" : "d-none"} d-xl-flex flex-column h-100`}>
          <CandidateSidebar candidates={candidates} selectedIdx={selectedIdx} onSelect={handleSelect} />
        </div>
        {selected ? (
          <>
            <div className={`${mobileView === "review" ? "d-flex" : "d-none"} d-xl-flex flex-column h-100`}>
              <ReviewPane candidate={selected} submitting={submitting} onDecision={handleDecision} />
            </div>
            <div className={`${mobileView === "pdf" ? "d-flex" : "d-none"} d-xl-flex flex-column h-100`}>
              <PdfPane contexts={selected.contexts} />
            </div>
          </>
        ) : (
          <div className="container py-5 text-center text-body-secondary">
            <h2 className="h5 text-body">All caught up</h2>
            <p className="small">Every candidate has a Pass 2 decision. Use the filters to revisit any of them.</p>
          </div>
        )}
      </div>
    </div>
  );
}
