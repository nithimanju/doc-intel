// Shapes shared between server/ (Node) and src/ (browser). Mirrors
// golden/candidates.jsonl, golden/questions.jsonl and corpus/manifest.json
// exactly -- see golden/schema.md for the authoritative schema.

export type AnswerType =
  | "single_fact"
  | "table_numeric"
  | "multi_hop"
  | "unanswerable"
  | "ambiguous";

export type Pass2Status = "pending" | "accepted" | "rejected" | "flagged_hard";

export interface SourceLocation {
  doc_id: string;
  page: number;
  region: string;
}

/** One row of golden/candidates.jsonl, as stored on disk. */
export interface Candidate {
  question: string;
  answer: string;
  answer_type: AnswerType;
  confidence: string;
  source: string;
  licence: string;
  source_locations: SourceLocation[];
  evidence_quotes: string[];
  notes: string;
  pass1_status: string;
  pass2_status: Pass2Status;
  pass2_status_reason?: string;
  question_id?: string;
}

export interface LocationContext extends SourceLocation {
  excerpt: string;
}

/** What GET /api/candidates returns: each candidate plus its page context. */
export interface CandidateWithContext extends Candidate {
  idx: number;
  contexts: LocationContext[];
}

/** One row of golden/questions.jsonl. */
export interface Question {
  id: string;
  question: string;
  answer: string;
  answer_type: AnswerType;
  source_locations: SourceLocation[];
  requires_corpus: true;
  notes: string;
}

export type DecisionAction = "accept" | "reject" | "flag" | "edit";

export interface DecisionRequest {
  idx: number;
  action: DecisionAction;
  /** action "reject": optional reason. action "edit": the new text. */
  reason?: string;
  question?: string;
  answer?: string;
}

export interface DecisionResponse {
  ok: true;
  candidate: CandidateWithContext;
}
