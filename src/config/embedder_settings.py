from src.config.config_items import to_index_configs
from src.config.settings import (
    EMBEDDING_BASE_URL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    EMBEDDING_NAME,
    EMBEDDING_VERSION,
    IS_EMBEDDING_NORMALIZE,
    IS_EMBEDDING_TRUNCATE,
)
from src.vo.index_vo import Embedder


def get_embedder_setting(created_by: str = "system") -> Embedder:
    return Embedder(
        name=EMBEDDING_NAME,
        version=EMBEDDING_VERSION,
        created_by=created_by,
        configs=to_index_configs(
            {
                "batch_size": EMBEDDING_BATCH_SIZE,
                "dimension": EMBEDDING_DIMENSION,
                "normalize": IS_EMBEDDING_NORMALIZE,
                "truncate": IS_EMBEDDING_TRUNCATE,
                "base_url": EMBEDDING_BASE_URL,
                "model_name": EMBEDDING_MODEL_NAME,
                "model_revision": EMBEDDING_MODEL_REVISION,
            }
        ),
    )
