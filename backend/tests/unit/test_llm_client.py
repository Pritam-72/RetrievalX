import pytest

from app.rag.llm_client import LLMAnswer, parse_llm_answer


def test_parse_llm_answer_accepts_required_json() -> None:
    result = parse_llm_answer(
        '{"answerable": true, "answer": "Paris. [1]", "citations": [1]}'
    )

    assert result == LLMAnswer(answerable=True, answer="Paris. [1]", citations=[1])


def test_parse_llm_answer_accepts_fenced_json() -> None:
    result = parse_llm_answer('```json\n{"answerable": false}\n```')

    assert result.answerable is False


def test_parse_llm_answer_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="required JSON schema"):
        parse_llm_answer("not json")
