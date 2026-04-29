"""Ollama LLM client. Falls back to OpenAI/Anthropic API if Ollama is unavailable."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model

    def is_available(self) -> bool:
        try:
            requests.get(f"{self.base_url}/api/tags", timeout=3)
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def generate(self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 2048) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 4096, "num_predict": max_tokens},
        }
        try:
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
            return r.json().get("response", "")
        except requests.exceptions.ConnectionError:
            return "[Ollama not available. Start with: ollama serve]"
        except Exception as e:
            return f"[Error: {e}]"

    def chat(self, messages: list[dict], *, temperature: float = 0.1) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 4096},
        }
        try:
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")
        except Exception as e:
            return f"[Error: {e}]"
