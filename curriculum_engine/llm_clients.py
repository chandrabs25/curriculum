"""Provider-backed LLM clients for planner and module expansion calls."""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
FIREWORKS_DEEPSEEK_V4_PRO = "accounts/fireworks/models/deepseek-v4-pro"
FIREWORKS_GPT_OSS_120B = "accounts/fireworks/models/gpt-oss-120b"


class FireworksAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


FireworksTransport = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class FireworksLLMClient:
    """OpenAI-compatible Fireworks chat client with JSON-schema output."""

    api_key: str | None = None
    model: str = FIREWORKS_DEEPSEEK_V4_PRO
    base_url: str = FIREWORKS_BASE_URL
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout_seconds: float = 120.0
    max_retries: int = 3
    base_retry_seconds: float = 1.0
    transport: FireworksTransport | None = None

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        load_env_file("FIREWORKS_API_KEY")
        api_key = self.api_key or os.getenv("FIREWORKS_API_KEY")
        if not api_key and not self.transport:
            raise RuntimeError("FIREWORKS_API_KEY is not set")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You return valid JSON only. Do not include markdown or prose outside JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "StructuredOutput",
                    "schema": schema,
                    "strict": True,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.transport(payload) if self.transport else self._post_json(payload, api_key or "")
                content = _message_content(response)
                return parse_llm_json(content)
            except Exception as exc:
                last_exc = exc
                if attempt >= self.max_retries or not _is_retryable(exc):
                    raise
                delay = self.base_retry_seconds * (2**attempt) + random.uniform(0, 0.25)
                time.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError("Fireworks request failed without an exception")

    def _post_json(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise FireworksAPIError(
                f"Fireworks API error {exc.code}: {body}",
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise FireworksAPIError(f"Fireworks API network error: {exc}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise FireworksAPIError(f"Fireworks API returned invalid JSON: {body}") from exc


def parse_llm_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        fixed_text = re.sub(r"\\u(?![0-9a-fA-F]{4})", r"\\\\u", text)
        try:
            value = json.loads(fixed_text)
        except json.JSONDecodeError:
            value = _parse_first_json_object(fixed_text)
            if value is None:
                raise
    if not isinstance(value, dict):
        raise ValueError("LLM JSON response must be an object")
    return value


def _parse_first_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def load_env_file(key: str) -> None:
    if os.getenv(key):
        return
    current = Path.cwd()
    for directory in [current, *current.parents]:
        env_path = directory / ".env"
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() == key:
                    os.environ[key] = value.strip().strip("'\"")
                    return
        except OSError:
            continue


def _message_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise FireworksAPIError(f"Fireworks response missing choices: {response}")
    first = choices[0]
    if not isinstance(first, dict):
        raise FireworksAPIError(f"Fireworks response choice is invalid: {response}")
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(first.get("text"), str):
        return first["text"]
    raise FireworksAPIError(f"Fireworks response missing message content: {response}")


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, FireworksAPIError):
        return exc.status_code in {408, 409, 425, 429, 500, 502, 503, 504} or exc.status_code is None
    text = str(exc).lower()
    return any(marker in text for marker in ("timeout", "temporar", "rate limit", "429", "503", "unavailable"))


def _is_retryable(exc: Exception) -> bool:
    return _is_transient(exc) or isinstance(exc, (json.JSONDecodeError, ValueError))
