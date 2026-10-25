"""One-off: render specific (doc_id, page_num) pairs to PNG for manual multi-hop construction."""
from __future__ import annotations
import sys
from pathlib import Path
import pymupdf
import json

manifest = json.loads(Path("corpus/manifest.json").read_text(encoding="utf-8-sig"))
raw_path_by_doc = {d["doc_id"]: d["raw_path"] for d in manifest["documents"]}

pairs = [
    ("faa-71377", [498, 492]),
    ("faa-71377", [130, 131, 132]),
    ("faa-71377", [239, 240]),
    ("faa-71377", [328, 329]),
    ("faa-71377", [477, 478]),
    ("faa-71377", [554, 556]),
    ("faa-71377", [569, 570]),
    ("faa-71377", [338, 340]),
]

out_dir = Path("corpus/.cache/multihop_images")
out_dir.mkdir(parents=True, exist_ok=True)
opened = {}
for doc_id, pages in pairs:
    if doc_id not in opened:
        opened[doc_id] = pymupdf.open(raw_path_by_doc[doc_id])
    pdf = opened[doc_id]
    for p in pages:
        pix = pdf[p - 1].get_pixmap(dpi=150)
        out_path = out_dir / f"{doc_id}__p{p}.png"
        pix.save(out_path)
        print(out_path)
for pdf in opened.values():
    pdf.close()
