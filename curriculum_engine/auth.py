"""Supabase Auth verification helpers for FastAPI endpoints."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str = ""
    display_name: str = ""
    avatar_url: str = ""
    provider: str = "google"
    role: str = ""

    def to_profile(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "provider": self.provider or "google",
        }


class AuthVerifier(Protocol):
    def verify(self, token: str) -> AuthUser:
        ...


@dataclass
class StaticAuthVerifier:
    user: AuthUser = AuthUser(user_id="test-user", email="test@example.com", display_name="Test User")

    def verify(self, token: str) -> AuthUser:
        if not token:
            raise AuthError("Missing bearer token")
        return self.user


@dataclass
class SupabaseAuthVerifier:
    supabase_url: str
    jwt_secret: str | None = None
    audience: str = "authenticated"
    _jwks_client: Any = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "SupabaseAuthVerifier":
        url = os.getenv("SUPABASE_URL") or ""
        return cls(
            supabase_url=url.rstrip("/"),
            jwt_secret=os.getenv("SUPABASE_JWT_SECRET") or None,
        )

    def verify(self, token: str) -> AuthUser:
        if not token:
            raise AuthError("Missing bearer token")
        if not self.supabase_url and not self.jwt_secret:
            raise AuthError("SUPABASE_URL is not configured")

        claims = self._decode_with_jwks(token)
        return _claims_to_user(claims)

    def _decode_with_jwks(self, token: str) -> dict[str, Any]:
        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError as exc:
            raise AuthError("PyJWT is required for Supabase Auth verification") from exc

        errors: list[Exception] = []
        if self.supabase_url:
            try:
                if self._jwks_client is None:
                    self._jwks_client = PyJWKClient(
                        f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
                    )
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256", "EdDSA"],
                    audience=self.audience,
                )
            except Exception as exc:  # noqa: BLE001 - fall back to legacy HS secret when configured.
                errors.append(exc)

        if self.jwt_secret:
            try:
                return jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=["HS256"],
                    audience=self.audience,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        detail = errors[-1] if errors else "unknown verification error"
        raise AuthError(f"Invalid Supabase access token: {detail}")


def _claims_to_user(claims: dict[str, Any]) -> AuthUser:
    user_id = str(claims.get("sub") or "")
    if not user_id:
        raise AuthError("Supabase token is missing sub claim")
    metadata = claims.get("user_metadata") if isinstance(claims.get("user_metadata"), dict) else {}
    app_metadata = claims.get("app_metadata") if isinstance(claims.get("app_metadata"), dict) else {}
    providers = app_metadata.get("providers") if isinstance(app_metadata.get("providers"), list) else []
    provider = str(providers[0]) if providers else str(app_metadata.get("provider") or "google")
    display_name = str(
        metadata.get("full_name")
        or metadata.get("name")
        or metadata.get("display_name")
        or claims.get("email")
        or ""
    )
    return AuthUser(
        user_id=user_id,
        email=str(claims.get("email") or ""),
        display_name=display_name,
        avatar_url=str(metadata.get("avatar_url") or metadata.get("picture") or ""),
        provider=provider,
        role="",
    )
