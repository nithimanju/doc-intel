"""Fast human review loop for golden candidates (Step 4 of
docs/golden-set-method.md).

Two passes, run separately so they use different attention modes:
  --pass 1  question quality only (wording, specificity, no leaks) -- fast
  --pass 2  answer verification against the source page -- the irreducible
            work; per the method doc this is the only step that may never
            be automated.

On accept, the candidate is written into golden/questions.jsonl in the
final schema (see golden/schema.md) and marked accepted in candidates.jsonl.
Reject/flag/skip just update status in candidates.jsonl so a re-run resumes
from where you left off.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import msvcrt

    def read_key() -> str:
        return msvcrt.getch().decode(errors="replace").lower()

except ImportError:  # non-Windows fallback
    import tty
    import termios

    def read_key() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch.lower()


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def next_question_id(questions: list[dict]) -> str:
    nums = [int(q["id"][1:]) for q in questions if q.get("id", "").startswith("q") and q["id"][1:].isdigit()]
    return f"q{(max(nums) + 1) if nums else 1:03d}"


def page_excerpt(catalog_index: dict[tuple[str, int], str], doc_id: str, page: int, around: str) -> str:
    text = catalog_index.get((doc_id, page), "")
    if not around or around not in text:
        return text[:600]
    idx = text.find(around)
    start = max(0, idx - 200)
    end = min(len(text), idx + len(around) + 200)
    return text[start:end]


def render_card(i: int, total: int, c: dict, pass_num: int, catalog_index: dict) -> None:
    locations = c.get("source_locations", [])
    loc_str = "; ".join(f"{loc.get('doc_id')} p.{loc.get('page')}" for loc in locations) or "(none -- out-of-scope source)"
    print("\n" + "=" * 78)
    print(
        f"[{i + 1}/{total}]  type: {c.get('answer_type')}   "
        f"source: {c.get('source')}  locations: {loc_str}  "
        f"confidence: {c.get('confidence')}"
    )
    print(f"Q: {c.get('question')}")
    print(f"A: {c.get('answer')}")
    for q in c.get("evidence_quotes", []):
        print(f'EVIDENCE: "{q}"')
    if c.get("notes"):
        print(f"NOTES: {c['notes']}")
    if c.get("licence") == "needs_review-manufacturer_authored_mandatory_disclosure":
        print("LICENCE: needs_review (NHTSA manufacturer-authored document -- see decisions.md)")
    if pass_num == 2:
        quotes = c.get("evidence_quotes", [])
        for idx, loc in enumerate(locations):
            around = quotes[idx] if idx < len(quotes) else (quotes[0] if quotes else "")
            excerpt = page_excerpt(catalog_index, loc.get("doc_id"), loc.get("page"), around)
            print("-" * 78)
            print(f"PAGE CONTEXT ({loc.get('doc_id')} p.{loc.get('page')}):\n{excerpt}")
    print("-" * 78)
    if pass_num == 1:
        print("[a]ccept-wording  [e]dit  [r]eject  [s]kip  [q]uit")
    else:
        print("[a]ccept  [e]dit  [r]eject  [s]kip  [f]lag-hard  [q]uit")


def run_review(candidates_path: Path, questions_path: Path, catalog_path: Path, pass_num: int) -> None:
    candidates = load_jsonl(candidates_path)
    questions = load_jsonl(questions_path)
    catalog_index: dict[tuple[str, int], str] = {}
    if catalog_path.exists():
        for row in load_jsonl(catalog_path):
            catalog_index[(row["doc_id"], row["page_num"])] = row["text"]

    status_field = "pass1_status" if pass_num == 1 else "pass2_status"
    required_prior = None if pass_num == 1 else "accepted"
    prior_field = "pass1_status"

    pending_idx = [
        i
        for i, c in enumerate(candidates)
        if c.get(status_field, "pending") == "pending"
        and (required_prior is None or c.get(prior_field) == required_prior)
    ]

    if not pending_idx:
        print(f"nothing pending for pass {pass_num}")
        return

    for count, i in enumerate(pending_idx):
        c = candidates[i]
        render_card(count, len(pending_idx), c, pass_num, catalog_index)
        while True:
            print("> ", end="", flush=True)
            key = read_key()
            print(key)
            if key == "a":
                c[status_field] = "accepted"
                if pass_num == 2:
                    qid = next_question_id(questions)
                    questions.append(
                        {
                            "id": qid,
                            "question": c["question"],
                            "answer": c["answer"],
                            "answer_type": c["answer_type"],
                            "source_locations": c.get("source_locations", []),
                            "requires_corpus": True,
                            "notes": f"licence={c.get('licence')}; {c.get('notes', '')}".strip("; "),
                        }
                    )
                    save_jsonl(questions_path, questions)
                save_jsonl(candidates_path, candidates)
                break
            if key == "e":
                for field in ("question", "answer"):
                    new_val = input(f"  new {field} (blank = keep \"{c.get(field, '')}\"): ")
                    if new_val.strip():
                        c[field] = new_val.strip()
                save_jsonl(candidates_path, candidates)
                render_card(count, len(pending_idx), c, pass_num, catalog_index)
                continue
            if key == "r":
                reason = input("  reject reason (optional): ")
                c[status_field] = "rejected"
                c[f"{status_field}_reason"] = reason
                save_jsonl(candidates_path, candidates)
                break
            if key == "s":
                break
            if key == "f" and pass_num == 2:
                c[status_field] = "flagged_hard"
                save_jsonl(candidates_path, candidates)
                break
            if key == "q":
                print("stopping; progress saved.")
                return
            print("  unrecognized key, try again")

    print(f"\npass {pass_num} review complete for this run.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=Path("golden/candidates.jsonl"))
    parser.add_argument("--questions", type=Path, default=Path("golden/questions.jsonl"))
    parser.add_argument("--catalog", type=Path, default=Path("corpus/.cache/page_catalog.jsonl"))
    parser.add_argument("--pass", dest="pass_num", type=int, choices=[1, 2], required=True)
    args = parser.parse_args(argv)
    run_review(args.candidates, args.questions, args.catalog, args.pass_num)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
