"""
agents/security.py — Cryptographic audit chain, HMAC signing,
prompt injection defense, and API key redaction.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from typing import Any

from agents.models import AuditEntry, SecurityWarning


# ---------------------------------------------------------------------------
# Injection Patterns
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(previous|all|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"disregard\s+(all|previous|your)", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"```\s*system", re.IGNORECASE),
    re.compile(r"(?:[A-Za-z0-9+/]{4}){10,}={0,2}"),   # base64 payloads ≥40 chars
    re.compile(r"act\s+as\s+(if\s+you\s+are|a\s+)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"override\s+(previous|all|prior)", re.IGNORECASE),
]

REDACT_PATTERN = re.compile(r"(sk-|gsk_|AIza)[A-Za-z0-9\-_]{10,}")


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

def sanitize_input(text: str) -> tuple[str, list[str]]:
    """
    Sanitize text before inserting into LLM prompts.
    Returns (sanitized_text, list_of_detected_patterns).
    Strips known prompt injection patterns.
    """
    detected: list[str] = []
    sanitized = text

    for pattern in INJECTION_PATTERNS:
        matches = pattern.findall(sanitized)
        if matches:
            detected.append(f"Pattern '{pattern.pattern}' matched: {matches[:3]}")
            sanitized = pattern.sub("[SANITIZED]", sanitized)

    return sanitized, detected


def redact_keys(text: str) -> str:
    """Redact API keys from any string (logs, errors, tracebacks)."""
    return REDACT_PATTERN.sub("[REDACTED]", text)


# ---------------------------------------------------------------------------
# Session Token & Key Derivation
# ---------------------------------------------------------------------------

def generate_session_token() -> str:
    return str(uuid.uuid4())


def derive_session_key(session_token: str) -> bytes:
    """Derive a 32-byte key from the session token using HKDF-SHA256."""
    import hashlib
    # Simple HKDF extract+expand (no external dependency)
    prk = hashlib.sha256(session_token.encode()).digest()
    info = b"disaster-response-audit-key"
    # HKDF expand: T(1) = HMAC-Hash(PRK, "" || info || 0x01)
    key = hmac.new(prk, info + b"\x01", hashlib.sha256).digest()
    return key


# ---------------------------------------------------------------------------
# Audit Chain
# ---------------------------------------------------------------------------

def _serialize_entry_for_hash(entry: dict[str, Any]) -> bytes:
    """Stable JSON serialization for hashing (exclude hmac_sig field)."""
    d = {k: v for k, v in entry.items() if k != "hmac_sig"}
    return json.dumps(d, sort_keys=True, default=str).encode()


class AuditChain:
    """
    Hash-linked, HMAC-signed audit log.
    Each entry contains:
      - prev_hash: SHA-256 of the previous entry's serialization
      - hmac_sig:  HMAC-SHA256(session_key, entry_without_sig)
    Tampering with any entry breaks the chain and/or HMAC verification.
    """

    def __init__(self, session_key: bytes):
        self._key = session_key
        self._entries: list[AuditEntry] = []
        self._prev_hash: str = "0" * 64

    def append(self, cycle: int, agent: str, input_data: Any,
               output_data: Any, confidence: float) -> AuditEntry:
        from datetime import datetime, timezone

        input_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        output_hash = hashlib.sha256(
            json.dumps(output_data, sort_keys=True, default=str).encode()
        ).hexdigest()

        entry_dict: dict[str, Any] = {
            "cycle": cycle,
            "agent": agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_hash": input_hash,
            "output_hash": output_hash,
            "confidence": confidence,
            "prev_hash": self._prev_hash,
        }

        sig = hmac.new(
            self._key,
            _serialize_entry_for_hash(entry_dict),
            hashlib.sha256,
        ).hexdigest()
        entry_dict["hmac_sig"] = sig

        entry = AuditEntry(**entry_dict)
        self._entries.append(entry)
        self._prev_hash = hashlib.sha256(
            _serialize_entry_for_hash(entry_dict)
        ).hexdigest()
        return entry

    def verify(self) -> bool:
        """Return True iff the entire chain is intact and all HMACs are valid."""
        prev = "0" * 64
        for entry in self._entries:
            d = {
                "cycle": entry.cycle,
                "agent": entry.agent,
                "timestamp": entry.timestamp,
                "input_hash": entry.input_hash,
                "output_hash": entry.output_hash,
                "confidence": entry.confidence,
                "prev_hash": entry.prev_hash,
            }
            # Check prev_hash linkage
            if entry.prev_hash != prev:
                return False
            # Check HMAC
            expected_sig = hmac.new(
                self._key,
                _serialize_entry_for_hash(d),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(entry.hmac_sig, expected_sig):
                return False
            prev = hashlib.sha256(_serialize_entry_for_hash(d)).hexdigest()
        return True

    def terminal_hash(self) -> str:
        return self._prev_hash

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def to_list(self) -> list[dict]:
        return [
            {
                "cycle": e.cycle,
                "agent": e.agent,
                "timestamp": e.timestamp,
                "input_hash": e.input_hash,
                "output_hash": e.output_hash,
                "confidence": e.confidence,
                "prev_hash": e.prev_hash,
                "hmac_sig": e.hmac_sig,
            }
            for e in self._entries
        ]
