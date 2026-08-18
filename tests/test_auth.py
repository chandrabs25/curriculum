from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from curriculum_engine.auth import SupabaseAuthVerifier


class SupabaseAuthVerifierTest(unittest.TestCase):
    def test_reuses_jwks_client_between_verifications(self) -> None:
        created_clients = []

        class FakeJWKClient:
            def __init__(self, url: str):
                self.url = url
                created_clients.append(self)

            def get_signing_key_from_jwt(self, token: str):
                del token
                return types.SimpleNamespace(key="public-key")

        fake_jwt = types.SimpleNamespace(
            PyJWKClient=FakeJWKClient,
            decode=lambda *args, **kwargs: {"sub": "learner:1"},
        )
        verifier = SupabaseAuthVerifier("https://example.supabase.co")

        with patch.dict("sys.modules", {"jwt": fake_jwt}):
            verifier.verify("token-one")
            verifier.verify("token-two")

        self.assertEqual(len(created_clients), 1)


if __name__ == "__main__":
    unittest.main()
