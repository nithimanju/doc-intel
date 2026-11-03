from __future__ import annotations

from typing import Any

from src.vo.index_vo import IndexConfig


def to_index_configs(values: dict[str, Any]) -> list[IndexConfig]:
    """One IndexConfig per setting; bools stored as 'true'/'false' to match .env."""
    return [
        IndexConfig(
            name=name,
            value=str(value).lower() if isinstance(value, bool) else str(value),
        )
        for name, value in values.items()
    ]
