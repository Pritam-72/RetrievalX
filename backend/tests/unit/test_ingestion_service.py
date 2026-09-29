from uuid import uuid4

import numpy as np

from app.models.entities import Document
from app.services.chunking_service import Chunk
from app.services.ingestion_service import build_chunk_rows


class FakeEmbedder:
    model_name = "fake-model"

    def embed_passages(self, passages: list[str]) -> np.ndarray:
        return np.ones((len(passages), 384), dtype=np.float32)


def test_build_chunk_rows_keeps_raw_content_and_embeds_context_header() -> None:
    document = Document(
        id=uuid4(),
        user_id=uuid4(),
        filename="notes.pdf",
        file_type="pdf",
        file_size=10,
        content_hash="hash",
        storage_path="uploads/file.pdf",
    )
    chunk = Chunk("raw content", 2, 2, "Methods", 2)

    rows = build_chunk_rows(document, [chunk], FakeEmbedder())

    assert rows[0].content == "raw content"
    assert rows[0].page_start == 2
    assert rows[0].chunk_metadata == {}
