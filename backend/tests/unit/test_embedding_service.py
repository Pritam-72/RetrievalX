import numpy as np

from app.services.embedding_service import BGE_QUERY_PREFIX, EmbeddingService


class FakeEmbeddingModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def encode(self, texts, **kwargs):
        self.calls.append({"texts": texts, **kwargs})
        vectors = np.zeros((len(texts), 384), dtype=np.float32)
        vectors[:, 0] = 1
        return vectors


def test_embedding_service_uses_query_prefix_and_normalized_384_vectors() -> None:
    service = EmbeddingService("fake-model")
    fake_model = FakeEmbeddingModel()
    service._model = fake_model

    passage_vectors = service.embed_passages(["passage"])
    query_vector = service.embed_query("question")

    assert passage_vectors.shape == (1, 384)
    assert query_vector.shape == (384,)
    assert np.isclose(np.linalg.norm(passage_vectors[0]), 1.0)
    assert np.isclose(np.linalg.norm(query_vector), 1.0)
    assert fake_model.calls[0]["texts"] == ["passage"]
    assert fake_model.calls[1]["texts"] == [BGE_QUERY_PREFIX + "question"]


def test_embedding_service_rejects_wrong_dimension() -> None:
    service = EmbeddingService("fake-model")

    class WrongDimensionModel:
        def encode(self, texts, **kwargs):
            return np.zeros((len(texts), 3), dtype=np.float32)

    service._model = WrongDimensionModel()

    try:
        service.embed_passages(["passage"])
    except ValueError as error:
        assert "384" in str(error)
    else:
        raise AssertionError("wrong embedding dimensions must be rejected")
