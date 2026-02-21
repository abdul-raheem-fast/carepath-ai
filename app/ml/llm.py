import os
from typing import Protocol

import requests


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
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
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
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()


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
