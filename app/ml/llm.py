import os
import time
from typing import Protocol

import requests


_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
_RETRY_ATTEMPTS = 2
_RETRY_DELAY_S = 1.5


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class FallbackLLM:
    def generate(self, prompt: str) -> str:
        return (
            "CarePath AI fallback response: "
            "This summary is generated locally because no external LLM key is configured.\n\n"
            + prompt[:800]
        )


class GroqLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:
        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                response = requests.post(
                    _GROQ_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a safe healthcare assistant. Never claim diagnosis certainty.",
                            },
                            {
                                "role": "user",
                                "content": prompt,
                            },
                        ],
                        "temperature": 0.2,
                        "max_tokens": 1024,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"].strip()
            except Exception as exc:
                last_exc = exc
                if attempt < _RETRY_ATTEMPTS:
                    time.sleep(_RETRY_DELAY_S)
        raise last_exc


def get_llm_provider() -> LLMProvider:
    # Read directly from os.environ every call — bypasses lru_cache on Settings.
    api_key = os.environ.get("GROQ_API_KEY", "")
    model   = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    provider = os.environ.get("DEFAULT_LLM_PROVIDER", "fallback")
    if provider == "groq" and api_key:
        return GroqLLM(api_key, model)
    # Fall back to cached settings as secondary source
    try:
        from app.backend.config import get_settings
        s = get_settings()
        if s.groq_api_key:
            return GroqLLM(s.groq_api_key, s.groq_model)
    except Exception:
        pass
    return FallbackLLM()
