"""TEI HTTP client (/embed, /info). Texts + opaque ids only — no ChunkRecord."""

from __future__ import annotations

import time
from typing import Any, Sequence

import requests
from requests import Session

from src.config.settings import (
    EMBEDDING_BASE_URL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSION,
    IS_EMBEDDING_NORMALIZE,
    IS_EMBEDDING_TRUNCATE,
)
from src.utils.logger import logger

_RETRYABLE = frozenset({429, 503})
_REJECT = frozenset({413, 422, 424})
_MAX_ATTEMPTS = 5
_TIMEOUT_S = 120

_EMBED_URL = f"{EMBEDDING_BASE_URL}/embed"
_INFO_URL = f"{EMBEDDING_BASE_URL}/info"


class EmbeddingFailedError(Exception):
    """TEI unreachable, unexpected HTTP, or malformed response after retries."""


def batch_texts(texts: list[str]) -> list[list[str]]:
    """Split texts into batches of EMBEDDING_BATCH_SIZE."""
    size = EMBEDDING_BATCH_SIZE
    return [texts[i : i + size] for i in range(0, len(texts), size)]


def _parse_vectors(payload: Any, expected: int) -> list[list[float]]:
    if isinstance(payload, list):
        vectors = payload
    elif isinstance(payload, dict) and "embeddings" in payload:
        vectors = payload["embeddings"]
    else:
        raise EmbeddingFailedError(f"unexpected /embed shape: {type(payload)!r}")

    if not isinstance(vectors, list) or len(vectors) != expected:
        got = len(vectors) if isinstance(vectors, list) else "?"
        raise EmbeddingFailedError(f"got {got} vectors for batch of {expected}")

    for i, v in enumerate(vectors):
        if not isinstance(v, list) or len(v) != EMBEDDING_DIMENSION:
            length = len(v) if isinstance(v, list) else type(v).__name__
            raise EmbeddingFailedError(
                f"vector[{i}] length {length}, expected {EMBEDDING_DIMENSION}"
            )
        if not all(isinstance(x, (int, float)) for x in v):
            raise EmbeddingFailedError(f"vector[{i}] has non-numeric values")
    return vectors


def _post_once(
    session: Session,
    texts: list[str],
    prompt_name: str | None,
) -> list[list[float]] | None:
    """One batch. Vectors on success, None on 413/422/424, else EmbeddingFailedError."""
    body: dict[str, Any] = {
        "inputs": texts,
        "normalize": IS_EMBEDDING_NORMALIZE,
        "truncate": IS_EMBEDDING_TRUNCATE,
    }
    if prompt_name:
        body["prompt_name"] = prompt_name

    last_err: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = session.post(_EMBED_URL, json=body, timeout=_TIMEOUT_S)
        except requests.RequestException as exc:
            last_err = exc
            logger.warning("TEI connection (%d/%d): %s", attempt, _MAX_ATTEMPTS, exc)
            if attempt == _MAX_ATTEMPTS:
                raise EmbeddingFailedError(
                    f"connection failed after {_MAX_ATTEMPTS} attempts: {exc}"
                ) from exc
            time.sleep(2**attempt)
            continue

        code, snippet = resp.status_code, resp.text[:300]

        if code in _REJECT:
            logger.warning("TEI reject HTTP %s: %s", code, snippet)
            return None

        if code in _RETRYABLE:
            logger.warning("TEI HTTP %s (%d/%d)", code, attempt, _MAX_ATTEMPTS)
            if attempt == _MAX_ATTEMPTS:
                raise EmbeddingFailedError(
                    f"HTTP {code} after {_MAX_ATTEMPTS} attempts: {snippet}"
                )
            time.sleep(2**attempt)
            continue

        if not resp.ok:
            raise EmbeddingFailedError(f"HTTP {code}: {snippet}")

        return _parse_vectors(resp.json(), expected=len(texts))

    raise EmbeddingFailedError(f"exhausted retries: {last_err}")


def _embed_batch(
    session: Session,
    texts: list[str],
    ids: Sequence[str],
    prompt_name: str | None,
) -> list[list[float] | None]:
    """On batch reject, retry items one-by-one so only bad slots become None."""
    vectors = _post_once(session, texts, prompt_name)
    if vectors is not None:
        return list(vectors)

    if len(texts) == 1:
        logger.warning("TEI skipped id=%s", ids[0])
        return [None]

    logger.warning("TEI rejected batch of %d; splitting", len(texts))
    out: list[list[float] | None] = []
    for text, item_id in zip(texts, ids, strict=True):
        one = _post_once(session, [text], prompt_name)
        if one is None:
            logger.warning("TEI skipped id=%s", item_id)
            out.append(None)
        else:
            out.append(one[0])
    return out


def _embed_all(
    texts: list[str],
    *,
    ids: Sequence[str] | None,
    prompt_name: str | None,
) -> list[list[float] | None]:
    if ids is None:
        ids = [str(i) for i in range(len(texts))]
    elif len(ids) != len(texts):
        raise ValueError(f"ids ({len(ids)}) != texts ({len(texts)})")

    out: list[list[float] | None] = []
    with Session() as session:
        offset = 0
        for batch in batch_texts(texts):
            batch_ids = ids[offset : offset + len(batch)]
            out.extend(_embed_batch(session, batch, batch_ids, prompt_name))
            offset += len(batch)

    if len(out) != len(texts):
        raise EmbeddingFailedError(
            f"alignment error: {len(out)} results for {len(texts)} texts"
        )
    return out


def embed_documents(
    texts: list[str],
    *,
    ids: Sequence[str] | None = None,
) -> list[list[float] | None]:
    """Document embed (no prompt). Same length as texts; None = rejected item."""
    return _embed_all(texts, ids=ids, prompt_name=None)


def embed_queries(
    texts: list[str],
    *,
    ids: Sequence[str] | None = None,
    prompt_name: str = "web_search_query",
) -> list[list[float] | None]:
    """Query embed with model-card prompt. Same length as texts; None = rejected."""
    return _embed_all(texts, ids=ids, prompt_name=prompt_name)


def service_info() -> dict[str, Any]:
    with Session() as session:
        try:
            resp = session.get(_INFO_URL, timeout=_TIMEOUT_S)
        except requests.RequestException as exc:
            raise EmbeddingFailedError(f"/info connection failed: {exc}") from exc
        if not resp.ok:
            raise EmbeddingFailedError(f"/info HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        if not isinstance(data, dict):
            raise EmbeddingFailedError(f"unexpected /info shape: {type(data)!r}")
        return data
