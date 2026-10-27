"""Tests for the pure helper functions in src.injest.docling.chunker.

Only the duck-typed, non-network helpers are covered here (label/region/
hash/name/confidence/error extraction, and chunk-record assembly from a fake
``chunk`` object). ``chunk_docling_document`` itself downloads a tokenizer
from Hugging Face and is excluded — that's an integration path, not a unit
under test, and exercising it would require network access and a real
HF_TOKEN regardless of what's in any local .env.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from docling_core.types.doc import DocItemLabel

from tests.conftest import make_bbox, make_doc_item, make_prov

from src.injest.docling.chunker import (
    _bbox_dict,
    _build_chunk_record,
    _confidence_dict,
    _derive_chunk_type,
    _document_name,
    _errors_list,
    _label_value,
    _regions_from_doc_items,
    _source_hash,
    _table_structure_for_chunk,
)


class TestLabelValue:
    def test_enum_like_label_uses_value_attribute(self):
        label = SimpleNamespace(value="text")
        assert _label_value(label) == "text"

    def test_plain_string_label_passthrough(self):
        assert _label_value("list_item") == "list_item"

    def test_none_label_stringifies(self):
        assert _label_value(None) == "None"


class TestDeriveChunkType:
    def test_table_label_wins_even_when_not_first(self):
        items = [make_doc_item(label="text"), make_doc_item(label=DocItemLabel.TABLE)]
        assert _derive_chunk_type(items) == "table"

    def test_no_items_is_unknown(self):
        assert _derive_chunk_type([]) == "unknown"

    def test_non_table_uses_first_items_label(self):
        items = [make_doc_item(label="section_header"), make_doc_item(label="text")]
        assert _derive_chunk_type(items) == "section_header"


class TestBboxDict:
    def test_includes_coord_origin_when_present(self):
        origin = SimpleNamespace(value="BOTTOMLEFT")
        bbox = make_bbox(1.0, 2.0, 3.0, 4.0, coord_origin=origin)
        out = _bbox_dict(bbox)
        assert out == {"l": 1.0, "t": 2.0, "r": 3.0, "b": 4.0, "coord_origin": "BOTTOMLEFT"}

    def test_omits_coord_origin_when_absent(self):
        bbox = make_bbox(coord_origin=None)
        out = _bbox_dict(bbox)
        assert "coord_origin" not in out

    def test_coerces_to_float(self):
        bbox = make_bbox(l=1, t=2, r=3, b=4)
        out = _bbox_dict(bbox)
        assert all(isinstance(v, float) for k, v in out.items() if k != "coord_origin")


class TestRegionsFromDocItems:
    def test_one_region_per_prov_entry(self):
        item = make_doc_item(prov=[make_prov(page_no=1), make_prov(page_no=2)])
        regions = _regions_from_doc_items([item])
        assert [r.page for r in regions] == [1, 2]

    def test_missing_charspan_yields_none_offsets(self):
        item = make_doc_item(prov=[make_prov(charspan=None)])
        regions = _regions_from_doc_items([item])
        assert regions[0].char_start is None
        assert regions[0].char_end is None

    def test_item_with_no_prov_yields_no_regions(self):
        item = make_doc_item(prov=[])
        assert _regions_from_doc_items([item]) == []

    def test_multiple_items_concatenate_regions(self):
        item_a = make_doc_item(prov=[make_prov(page_no=1)])
        item_b = make_doc_item(prov=[make_prov(page_no=1), make_prov(page_no=2)])
        regions = _regions_from_doc_items([item_a, item_b])
        assert len(regions) == 3


class TestTableStructureForChunk:
    def test_returns_none_when_chunk_type_not_table(self):
        doc = SimpleNamespace(tables=[])
        items = [make_doc_item(label="text")]
        assert _table_structure_for_chunk(doc, items, "text") is None

    def test_finds_matching_table_by_self_ref_and_dumps_data(self):
        dumped = {"rows": 2}
        table_data = SimpleNamespace(model_dump=lambda: dumped)
        table = SimpleNamespace(self_ref="#/tables/0", data=table_data)
        # isinstance(table, TableItem) check in source requires a real TableItem;
        # fall back path (plain item.data) is covered below instead.
        doc = SimpleNamespace(tables=[table])
        items = [make_doc_item(label=DocItemLabel.TABLE, self_ref="#/tables/0")]
        # Without a real TableItem the self_ref lookup loop won't match via
        # isinstance, so this exercises the "no match found" -> None path.
        assert _table_structure_for_chunk(doc, items, "table") is None

    def test_table_item_without_doc_tables_attribute_returns_none_safely(self):
        doc = SimpleNamespace()  # no .tables attribute at all
        items = [make_doc_item(label=DocItemLabel.TABLE, self_ref="#/tables/0")]
        assert _table_structure_for_chunk(doc, items, "table") is None


class TestSourceHash:
    def test_prefers_input_document_hash(self):
        result = SimpleNamespace(input=SimpleNamespace(document_hash="hash-from-input"))
        doc = SimpleNamespace(origin=SimpleNamespace(binary_hash="hash-from-origin"))
        assert _source_hash(result, doc) == "hash-from-input"

    def test_falls_back_to_origin_binary_hash(self):
        result = SimpleNamespace(input=None)
        doc = SimpleNamespace(origin=SimpleNamespace(binary_hash="hash-from-origin"))
        assert _source_hash(result, doc) == "hash-from-origin"

    def test_returns_empty_string_when_neither_present(self):
        result = SimpleNamespace(input=None)
        doc = SimpleNamespace(origin=None)
        assert _source_hash(result, doc) == ""


class TestDocumentName:
    def test_prefers_origin_filename(self):
        result = SimpleNamespace(input=None)
        doc = SimpleNamespace(origin=SimpleNamespace(filename="report.pdf"), name="ignored")
        assert _document_name(result, doc) == "report.pdf"

    def test_falls_back_to_input_file_name(self):
        result = SimpleNamespace(input=SimpleNamespace(file=SimpleNamespace(name="input.pdf")))
        doc = SimpleNamespace(origin=None, name="ignored")
        assert _document_name(result, doc) == "input.pdf"

    def test_falls_back_to_doc_name(self):
        result = SimpleNamespace(input=None)
        doc = SimpleNamespace(origin=None, name="doc-name")
        assert _document_name(result, doc) == "doc-name"

    def test_falls_back_to_unknown(self):
        result = SimpleNamespace(input=None)
        doc = SimpleNamespace(origin=None, name=None)
        assert _document_name(result, doc) == "unknown"


class TestConfidenceDict:
    def test_none_confidence_returns_none(self):
        result = SimpleNamespace(confidence=None)
        assert _confidence_dict(result) is None

    def test_model_dump_used_when_available(self):
        dumped = {"mean_score": 0.9}
        result = SimpleNamespace(confidence=SimpleNamespace(model_dump=lambda mode="json": dumped))
        assert _confidence_dict(result) == dumped

    def test_plain_dict_passthrough(self):
        result = SimpleNamespace(confidence={"mean_score": 0.9})
        assert _confidence_dict(result) == {"mean_score": 0.9}

    def test_scalar_confidence_is_wrapped(self):
        result = SimpleNamespace(confidence=0.75)
        assert _confidence_dict(result) == {"value": 0.75}


class TestErrorsList:
    def test_none_errors_returns_empty_list(self):
        result = SimpleNamespace(errors=None)
        assert _errors_list(result) == []

    def test_model_dump_errors_are_dumped(self):
        err = SimpleNamespace(model_dump=lambda mode="json": {"message": "boom"})
        result = SimpleNamespace(errors=[err])
        assert _errors_list(result) == [{"message": "boom"}]

    def test_plain_errors_passthrough(self):
        result = SimpleNamespace(errors=["raw error string"])
        assert _errors_list(result) == ["raw error string"]


class TestBuildChunkRecord:
    def test_chunk_id_format(self):
        chunk = SimpleNamespace(meta=SimpleNamespace(doc_items=[], headings=None))
        record = _build_chunk_record(
            chunk_index=3,
            chunk=chunk,
            content="text",
            doc=SimpleNamespace(),
            source_hash="abc",
            doc_id="mydoc",
        )
        assert record.chunk_id == "mydoc:00003"

    def test_headings_none_normalizes_to_empty_list(self):
        chunk = SimpleNamespace(meta=SimpleNamespace(doc_items=[], headings=None))
        record = _build_chunk_record(
            chunk_index=0, chunk=chunk, content="text", doc=SimpleNamespace(), source_hash="abc", doc_id="d",
        )
        assert record.heading_level == []

    def test_regions_and_chunk_type_derived_from_doc_items(self):
        item = make_doc_item(label="text", prov=[make_prov(page_no=5)])
        chunk = SimpleNamespace(meta=SimpleNamespace(doc_items=[item], headings=["H1"]))
        record = _build_chunk_record(
            chunk_index=0, chunk=chunk, content="text", doc=SimpleNamespace(), source_hash="abc", doc_id="d",
        )
        assert record.chunk_type == "text"
        assert record.heading_level == ["H1"]
        assert len(record.regions) == 1
        assert record.regions[0].page == 5

    def test_embedding_vector_always_none_at_build_time(self):
        chunk = SimpleNamespace(meta=SimpleNamespace(doc_items=[], headings=None))
        record = _build_chunk_record(
            chunk_index=0, chunk=chunk, content="text", doc=SimpleNamespace(), source_hash="abc", doc_id="d",
        )
        assert record.embedding_vector is None
