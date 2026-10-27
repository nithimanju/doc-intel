"""Shared fakes for Docling-shaped objects.

Chunker helpers duck-type on attributes (``getattr(item, "label", None)`` etc.)
rather than Docling's concrete classes, so plain ``SimpleNamespace`` objects
exercise the same code paths without needing a real conversion or model
download.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def make_bbox(l: float = 0.0, t: float = 10.0, r: float = 5.0, b: float = 0.0, coord_origin: Any = None) -> SimpleNamespace:
    return SimpleNamespace(l=l, t=t, r=r, b=b, coord_origin=coord_origin)


def make_prov(page_no: int = 1, bbox: Any = None, charspan: tuple[int | None, int | None] | None = (0, 10)) -> SimpleNamespace:
    return SimpleNamespace(page_no=page_no, bbox=bbox or make_bbox(), charspan=charspan)


def make_doc_item(label: Any = "text", prov: list[Any] | None = None, self_ref: str | None = None, data: Any = None) -> SimpleNamespace:
    return SimpleNamespace(label=label, prov=prov if prov is not None else [make_prov()], self_ref=self_ref, data=data)
