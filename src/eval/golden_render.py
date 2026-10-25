"""Render sampled pages (from golden_sample.py) to PNG images for visual
review during candidate generation (Step 2 of docs/golden-set-method.md).

Text extraction alone misses table alignment and figures/diagrams; this
lets the generator actually look at the page the way a human reviewer would.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sampled", type=Path, default=Path("corpus/.cache/sampled_pages.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("corpus/.cache/page_images"))
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in args.sampled.read_text(encoding="utf-8").splitlines()]

    opened: dict[str, pymupdf.Document] = {}
    rendered = 0
    index: list[dict] = []
    for r in rows:
        doc_id = r["doc_id"]
        if doc_id not in opened:
            opened[doc_id] = pymupdf.open(r["raw_path"])
        pdf = opened[doc_id]
        page = pdf[r["page_num"] - 1]
        pix = page.get_pixmap(dpi=args.dpi)
        out_path = args.out_dir / f"{doc_id}__p{r['page_num']}.png"
        pix.save(out_path)
        index.append({**r, "image_path": str(out_path)})
        rendered += 1

    for pdf in opened.values():
        pdf.close()

    index_path = args.sampled.with_name(args.sampled.stem + "_with_images.jsonl")
    with index_path.open("w", encoding="utf-8") as fh:
        for r in index:
            fh.write(json.dumps(r) + "\n")

    print(f"rendered {rendered} page images -> {args.out_dir}")
    print(f"index with image paths -> {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
