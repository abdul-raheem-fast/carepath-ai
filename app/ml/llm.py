from typing import Protocol

import requests

from app.backend.config import get_settings


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
    settings = get_settings()
    if settings.default_llm_provider == "groq" and settings.groq_api_key:
        return GroqLLM(settings.groq_api_key, settings.groq_model)
    return FallbackLLM()
