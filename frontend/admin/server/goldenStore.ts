import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fromRepoRoot } from "./paths.ts";
import type { Candidate, DecisionRequest, Question } from "../shared/types.ts";
import type { ContextCache } from "./contextCache.ts";

const CANDIDATES_PATH = fromRepoRoot("golden", "candidates.jsonl");
const QUESTIONS_PATH = fromRepoRoot("golden", "questions.jsonl");

function loadJsonl<T>(path: string): T[] {
  if (!existsSync(path)) return [];
  const text = readFileSync(path, "utf-8");
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as T);
}

function saveJsonl<T>(path: string, rows: T[]): void {
  const text = rows.map((r) => JSON.stringify(r)).join("\n") + (rows.length ? "\n" : "");
  writeFileSync(path, text, "utf-8");
}

function nextQuestionId(questions: Question[]): string {
  const nums = questions
    .map((q) => q.id)
    .filter((id) => /^q\d+$/.test(id))
    .map((id) => parseInt(id.slice(1), 10));
  const next = nums.length ? Math.max(...nums) + 1 : 1;
  return `q${String(next).padStart(3, "0")}`;
}

export class GoldenStore {
  private candidates: Candidate[] = [];
  private questions: Question[] = [];

  load(): void {
    this.candidates = loadJsonl<Candidate>(CANDIDATES_PATH);
    this.questions = loadJsonl<Question>(QUESTIONS_PATH);
  }

  count(): number {
    return this.candidates.length;
  }

  listCandidates(): Candidate[] {
    return this.candidates;
  }

  getCandidate(idx: number): Candidate {
    const c = this.candidates[idx];
    if (!c) throw new RangeError(`no candidate at idx ${idx}`);
    return c;
  }

  withContext(idx: number, cache: ContextCache) {
    const c = this.getCandidate(idx);
    const contexts = c.source_locations.map((loc, i) => {
      const around = c.evidence_quotes[i] ?? c.evidence_quotes[0] ?? "";
      return { ...loc, excerpt: cache.excerpt(loc.doc_id, loc.page, around) };
    });
    return { ...c, idx, contexts };
  }

  private saveBoth(): void {
    saveJsonl(CANDIDATES_PATH, this.candidates);
    saveJsonl(QUESTIONS_PATH, this.questions);
  }

  /** Writes or overwrites `c`'s entry in questions.jsonl under its existing
   * question_id (patch-in-place), matching the user's chosen semantics for
   * re-editing an already-accepted candidate. */
  private upsertQuestion(c: Candidate): void {
    const row: Question = {
      id: c.question_id!,
      question: c.question,
      answer: c.answer,
      answer_type: c.answer_type,
      source_locations: c.source_locations,
      requires_corpus: true,
      notes: `licence=${c.licence}; ${c.notes}`.replace(/^;\s*|;\s*$/g, ""),
    };
    const existingIdx = this.questions.findIndex((q) => q.id === c.question_id);
    if (existingIdx === -1) this.questions.push(row);
    else this.questions[existingIdx] = row;
  }

  applyDecision(req: DecisionRequest): Candidate {
    const c = this.getCandidate(req.idx);

    switch (req.action) {
      case "accept": {
        if (!c.question_id) c.question_id = nextQuestionId(this.questions);
        c.pass2_status = "accepted";
        delete c.pass2_status_reason;
        this.upsertQuestion(c);
        break;
      }
      case "reject": {
        c.pass2_status = "rejected";
        if (req.reason) c.pass2_status_reason = req.reason;
        break;
      }
      case "flag": {
        c.pass2_status = "flagged_hard";
        break;
      }
      case "edit": {
        if (req.question !== undefined && req.question.trim()) c.question = req.question.trim();
        if (req.answer !== undefined && req.answer.trim()) c.answer = req.answer.trim();
        // Already accepted: keep questions.jsonl in sync with the edit
        // immediately, per the user's chosen "patch in place" semantics.
        if (c.question_id) this.upsertQuestion(c);
        break;
      }
    }

    this.saveBoth();
    return c;
  }
}
