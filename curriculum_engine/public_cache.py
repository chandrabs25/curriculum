"""Shared cache helpers for public, non-personalized API responses."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


CACHE_VERSION = os.getenv("CURRICULUM_PUBLIC_CACHE_VERSION", "public-cache-v1")
INTENT_CACHE_VERSION = os.getenv("CURRICULUM_INTENT_CACHE_VERSION", "intent-v2")
RETRIEVAL_CACHE_VERSION = os.getenv("CURRICULUM_RETRIEVAL_CACHE_VERSION", "retrieval-v2")
PLAN_CACHE_VERSION = os.getenv("CURRICULUM_PLAN_CACHE_VERSION", "plan-v2")


def public_cache_enabled() -> bool:
    return os.getenv("CURRICULUM_PUBLIC_CACHE", "1").strip().lower() not in {"0", "false", "no", "off"}


def ttl_seconds(kind: str) -> int:
    env_key = f"CURRICULUM_{kind.upper()}_CACHE_TTL_SECONDS"
    default = {
        "intent": 7 * 24 * 60 * 60,
        "retrieval": 24 * 60 * 60,
        "plan": 6 * 60 * 60,
    }.get(kind, 60 * 60)
    try:
        return max(0, int(os.getenv(env_key, str(default))))
    except ValueError:
        return default


def expires_at_for(kind: str) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds(kind))).isoformat()


def normalize_query(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text)
    prefixes = [
        "i want to learn about ",
        "i want to learn ",
        "i need to learn about ",
        "i need to learn ",
        "teach me about ",
        "teach me ",
        "learn about ",
        "learn ",
    ]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix) :].strip()
                changed = True
    return re.sub(r"\s+", " ", text)


def intent_cache_key(payload: Any) -> str:
    request = _model_dump(payload)
    request["query"] = normalize_query(str(request.get("query") or ""))
    return _cache_key("intent", INTENT_CACHE_VERSION, request)


def retrieval_cache_key(payload: Any) -> str:
    request = _curriculum_payload_key(payload)
    return _cache_key("retrieval", RETRIEVAL_CACHE_VERSION, request)


def plan_cache_key(payload: Any) -> str:
    request = _curriculum_payload_key(payload)
    return _cache_key("plan", PLAN_CACHE_VERSION, request)


def is_public_curriculum_cacheable(payload: Any) -> bool:
    request = _model_dump(payload)
    return not request.get("learner_state") and request.get("prerequisite_check") in (None, {}, [])


def fresh_guest_plan_response(row: dict[str, Any]) -> dict[str, Any]:
    fresh = copy.deepcopy(row)
    fresh["curriculum_plan_id"] = "curriculum_plan:" + uuid.uuid4().hex[:16]
    fresh["learner_id"] = "guest"
    fresh["created_at"] = datetime.now(timezone.utc).isoformat()
    metadata = fresh.get("metadata") if isinstance(fresh.get("metadata"), dict) else {}
    metadata = dict(metadata)
    metadata["cache_template_id"] = row.get("curriculum_plan_id") or ""
    fresh["metadata"] = metadata
    return fresh


def _curriculum_payload_key(payload: Any) -> dict[str, Any]:
    request = _model_dump(payload)
    onboarding = request.get("onboarding") if isinstance(request.get("onboarding"), dict) else {}
    topic = str(onboarding.get("topic") or "")
    onboarding = dict(onboarding)
    onboarding["topic"] = normalize_query(topic)
    request["onboarding"] = onboarding
    return request


def _cache_key(kind: str, version: str, request: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "cache_version": CACHE_VERSION,
            "kind_version": version,
            "kind": kind,
            "request": request,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"{kind}:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _model_dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if isinstance(payload, dict):
        return copy.deepcopy(payload)
    return copy.deepcopy(getattr(payload, "__dict__", {}))
