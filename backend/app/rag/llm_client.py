import json
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError


class LLMAnswer(BaseModel):
    answerable: bool
    answer: str = ""
    citations: list[int] = Field(default_factory=list)


class LLMClient(Protocol):
    async def generate(self, system_prompt: str, user_message: str) -> str:
        """Generate a structured response from the provider."""


class GeminiLLMClient:
    def __init__(self, api_key: str, model: str, timeout: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def generate(self, system_prompt: str, user_message: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url, params={"key": self.api_key}, json=payload
            )
            response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


class OllamaLLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_message,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
        return response.json()["response"]


class StubLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    async def generate(self, system_prompt: str, user_message: str) -> str:
        self.calls += 1
        return self.response


def create_llm_client(
    provider: str, model: str, api_key: str, base_url: str
) -> LLMClient:
    if provider == "gemini":
        if not api_key or not model:
            raise ValueError("GEMINI_API_KEY and LLM_MODEL are required for Gemini")
        return GeminiLLMClient(api_key, model)
    if provider == "ollama":
        if not model:
            raise ValueError("LLM_MODEL is required for Ollama")
        return OllamaLLMClient(base_url, model)
    if provider == "stub":
        return StubLLMClient('{"answerable": false, "answer": "", "citations": []}')
    raise ValueError(f"Unsupported LLM provider: {provider}")


def parse_llm_answer(raw: str) -> LLMAnswer:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = (
            cleaned.removeprefix("```").removeprefix("json").removesuffix("```").strip()
        )
    try:
        return LLMAnswer.model_validate_json(cleaned)
    except (ValidationError, json.JSONDecodeError) as error:
        raise ValueError(
            "LLM response did not match the required JSON schema"
        ) from error
