from src.config.config_items import to_index_configs
from src.config.settings import CHUNK_MAX_TOKEN_LIMIT, CHUNK_NAME, CHUNKER_VERSION
from src.vo.index_vo import Chunker


def get_chunker_setting(created_by: str = "system") -> Chunker:
    return Chunker(
        name=CHUNK_NAME,
        version=CHUNKER_VERSION,
        created_by=created_by,
        configs=to_index_configs({"max_token_limit": CHUNK_MAX_TOKEN_LIMIT}),
    )
