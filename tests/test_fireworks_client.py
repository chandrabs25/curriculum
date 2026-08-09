from __future__ import annotations

import unittest
import tempfile
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from curriculum_engine import (
    FIREWORKS_GPT_OSS_120B,
    FIREWORKS_MINIMAX_M2P7,
    INTENT_OUTPUT_MAX_TOKENS,
    FireworksAPIError,
    FireworksLLMClient,
    parse_llm_json,
)


class FireworksClientTest(unittest.TestCase):
    def test_generate_json_uses_minimax_model_and_schema(self) -> None:
        calls: list[dict[str, Any]] = []

        def transport(payload: dict[str, Any]) -> dict[str, Any]:
            calls.append(payload)
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        client = FireworksLLMClient(api_key="test-key", transport=transport)
        result = client.generate_json(
            "Return JSON",
            {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0]["model"], FIREWORKS_MINIMAX_M2P7)
        self.assertEqual(calls[0]["response_format"]["type"], "json_schema")
        self.assertEqual(calls[0]["response_format"]["json_schema"]["name"], "StructuredOutput")
        self.assertTrue(calls[0]["response_format"]["json_schema"]["strict"])
        self.assertEqual(calls[0]["messages"][0]["role"], "system")
        self.assertIn("valid JSON only", calls[0]["messages"][0]["content"])

    def test_generate_json_uses_json_object_without_schema(self) -> None:
        def transport(payload: dict[str, Any]) -> dict[str, Any]:
            self.assertEqual(payload["response_format"], {"type": "json_object"})
            return {"choices": [{"message": {"content": '{"answer": 1}'}}]}

        self.assertEqual(FireworksLLMClient(api_key="test-key", transport=transport).generate_json("Return JSON"), {"answer": 1})

    def test_gpt_oss_120b_model_can_be_configured_for_intent_classification(self) -> None:
        calls: list[dict[str, Any]] = []

        def transport(payload: dict[str, Any]) -> dict[str, Any]:
            calls.append(payload)
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        client = FireworksLLMClient(
            api_key="test-key",
            model=FIREWORKS_GPT_OSS_120B,
            max_tokens=INTENT_OUTPUT_MAX_TOKENS,
            transport=transport,
        )

        self.assertEqual(client.generate_json("Return JSON"), {"ok": True})
        self.assertEqual(calls[0]["model"], FIREWORKS_GPT_OSS_120B)
        self.assertEqual(calls[0]["max_tokens"], INTENT_OUTPUT_MAX_TOKENS)

    def test_retries_transient_errors(self) -> None:
        attempts = 0

        def transport(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise FireworksAPIError("busy", status_code=503)
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        client = FireworksLLMClient(
            api_key="test-key",
            transport=transport,
            max_retries=1,
            base_retry_seconds=0,
        )

        self.assertEqual(client.generate_json("Return JSON"), {"ok": True})
        self.assertEqual(attempts, 2)

    def test_retry_count_can_be_configured_by_environment(self) -> None:
        attempts = 0
        old_retries = os.environ.get("FIREWORKS_MAX_RETRIES")
        old_delay = os.environ.get("FIREWORKS_BASE_RETRY_SECONDS")
        os.environ["FIREWORKS_MAX_RETRIES"] = "2"
        os.environ["FIREWORKS_BASE_RETRY_SECONDS"] = "0"

        def transport(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise FireworksAPIError("service overloaded", status_code=503)
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        try:
            client = FireworksLLMClient(
                api_key="test-key",
                transport=transport,
                max_retries=0,
                base_retry_seconds=10,
            )
            self.assertEqual(client.generate_json("Return JSON"), {"ok": True})
            self.assertEqual(attempts, 3)
        finally:
            if old_retries is None:
                os.environ.pop("FIREWORKS_MAX_RETRIES", None)
            else:
                os.environ["FIREWORKS_MAX_RETRIES"] = old_retries
            if old_delay is None:
                os.environ.pop("FIREWORKS_BASE_RETRY_SECONDS", None)
            else:
                os.environ["FIREWORKS_BASE_RETRY_SECONDS"] = old_delay

    def test_retries_urlopen_timeout(self) -> None:
        attempts = 0

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}'

        def fake_urlopen(request: object, timeout: float) -> FakeResponse:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise TimeoutError("The read operation timed out")
            return FakeResponse()

        client = FireworksLLMClient(
            api_key="test-key",
            max_retries=1,
            base_retry_seconds=0,
        )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.assertEqual(client.generate_json("Return JSON"), {"ok": True})
        self.assertEqual(attempts, 2)

    def test_post_json_sends_browser_compatible_headers(self) -> None:
        captured_headers: dict[str, str] = {}

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"{\\"ok\\": true}"}}]}'

        def fake_urlopen(request: object, timeout: float) -> FakeResponse:
            captured_headers.update(dict(request.header_items()))  # type: ignore[attr-defined]
            return FakeResponse()

        client = FireworksLLMClient(api_key="test-key", max_retries=0)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.assertEqual(client.generate_json("Return JSON"), {"ok": True})

        self.assertIn("Mozilla/5.0", captured_headers["User-agent"])
        self.assertEqual(captured_headers["Origin"], "https://curriculum-frontend.22f3002048.workers.dev")
        self.assertEqual(captured_headers["Referer"], "https://curriculum-frontend.22f3002048.workers.dev/")

    def test_retries_malformed_json(self) -> None:
        attempts = 0

        def transport(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return {"choices": [{"message": {"content": "{bad json"}}]}
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

        client = FireworksLLMClient(
            api_key="test-key",
            transport=transport,
            max_retries=1,
            base_retry_seconds=0,
        )

        self.assertEqual(client.generate_json("Return JSON"), {"ok": True})
        self.assertEqual(attempts, 2)

    def test_parse_llm_json_strips_markdown_and_reasoning(self) -> None:
        text = """```json
<think>hidden reasoning</think>
{"modules": []}
```"""

        self.assertEqual(parse_llm_json(text), {"modules": []})

    def test_parse_llm_json_uses_first_complete_object(self) -> None:
        text = '{"ok": true} trailing note that should be ignored'

        self.assertEqual(parse_llm_json(text), {"ok": True})

    def test_loads_fireworks_key_from_env_file(self) -> None:
        old_key = os.environ.pop("FIREWORKS_API_KEY", None)
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                Path(tmp, ".env").write_text("FIREWORKS_API_KEY=file-key\n", encoding="utf-8")
                os.chdir(tmp)

                def transport(payload: dict[str, Any]) -> dict[str, Any]:
                    return {"choices": [{"message": {"content": '{"ok": true}'}}]}

                self.assertEqual(FireworksLLMClient(transport=transport).generate_json("Return JSON"), {"ok": True})
                self.assertEqual(os.environ.get("FIREWORKS_API_KEY"), "file-key")
            finally:
                os.chdir(old_cwd)
                if old_key is not None:
                    os.environ["FIREWORKS_API_KEY"] = old_key
                else:
                    os.environ.pop("FIREWORKS_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
