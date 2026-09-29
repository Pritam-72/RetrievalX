from functools import lru_cache
from typing import Any

import numpy as np

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
EMBEDDING_DIM = 384
EMBEDDING_BATCH_SIZE = 32


class EmbeddingService:
    def __init__(self, model_name: str, batch_size: int = EMBEDDING_BATCH_SIZE) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._model: Any | None = None

    def embed_passages(self, passages: list[str]) -> np.ndarray:
        return self._encode(passages)

    def embed_query(self, question: str) -> np.ndarray:
        return self._encode([BGE_QUERY_PREFIX + question])[0]

    def _encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        vectors = self._get_model().encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        result = np.asarray(vectors, dtype=np.float32)
        if result.ndim == 1:
            result = result.reshape(1, -1)
        if result.shape[1] != EMBEDDING_DIM:
            raise ValueError(f"Expected {EMBEDDING_DIM}-dimensional embeddings")
        return result

    def _get_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model


@lru_cache
def get_embedding_service(model_name: str) -> EmbeddingService:
    return EmbeddingService(model_name)
