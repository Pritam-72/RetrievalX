import inspect

from app.rag.retriever import Retriever


def test_retriever_requires_user_and_document_scope() -> None:
    signature = inspect.signature(Retriever.search)

    assert signature.parameters["user_id"].default is inspect.Parameter.empty
    assert signature.parameters["document_ids"].default is inspect.Parameter.empty
