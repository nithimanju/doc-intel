import hashlib
import json

from src.config.chunker_settings import get_chunker_setting
from src.config.embedder_settings import get_embedder_setting
from src.config.parser_settings import get_parser_setting
from src.config.settings import INDEX_VERSION_ID
from src.vo.index_vo import IndexVersion


def _derived_version(chunker, parser, embedder) -> str:
    """Stable label from component names, versions and configs: same settings, same label."""
    payload = [
        [c.name, c.version, sorted((i.name, i.value) for i in c.configs)]
        for c in (chunker, parser, embedder)
    ]
    digest = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
    return f"idx-{digest[:12]}"


def get_index_setting(created_by: str = "system") -> IndexVersion:
    chunker = get_chunker_setting(created_by)
    parser = get_parser_setting(created_by)
    embedder = get_embedder_setting(created_by)
    return IndexVersion(
        version=INDEX_VERSION_ID or _derived_version(chunker, parser, embedder),
        chunker=chunker,
        embedder=embedder,
        parser=parser,
        created_by=created_by,
    )
