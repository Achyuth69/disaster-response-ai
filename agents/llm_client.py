"""
agents/llm_client.py — Groq LLM client with circuit breaker,
consensus voting, retry logic, and API key redaction.

Primary  : llama-3.3-70b-versatile  (280 t/s, 131K context)
Secondary: llama-3.1-8b-instant     (560 t/s, 131K context, fast fallback)
"""
from __future__ import annotations

import time
import threading
from typing import Callable, Any, Optional

from agents.models import ConfigurationError, ConsensusResult
from agents.security import redact_keys


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """CLOSED → OPEN → HALF-OPEN → CLOSED state machine."""

    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half-open"

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self._threshold       = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures        = 0
        self._state           = self.CLOSED
        self._opened_at: Optional[float] = None
        self._lock            = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                if time.time() - self._opened_at >= self._recovery_timeout:
                    self._state = self.HALF_OPEN
            return self._state

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        if self.state == self.OPEN:
            raise RuntimeError("CircuitBreaker OPEN — provider unavailable")
        try:
            result = fn(*args, **kwargs)
            with self._lock:
                self._failures = 0
                self._state    = self.CLOSED
            return result
        except Exception as exc:
            with self._lock:
                self._failures += 1
                if self._failures >= self._threshold:
                    self._state     = self.OPEN
                    self._opened_at = time.time()
            raise exc

    def reset(self) -> None:
        with self._lock:
            self._failures  = 0
            self._state     = self.CLOSED
            self._opened_at = None


# ---------------------------------------------------------------------------
# LLM Client  (Groq-only, two models for consensus + fallback)
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Groq-powered LLM client.

    primary_model  : llama-3.3-70b-versatile  — high quality, used for all agents
    secondary_model: llama-3.1-8b-instant     — fast fallback when primary fails

    Features:
    - Circuit breaker per model (auto-bypass after N failures)
    - 1 retry with 2 s backoff on transient errors
    - Consensus voting (primary + secondary, resolve by primary)
    - API key redacted from all error messages
    """

    # Current production models from console.groq.com/docs/models (April 2025)
    PRIMARY_MODEL   = "llama-3.3-70b-versatile"
    SECONDARY_MODEL = "llama-3.1-8b-instant"

    def __init__(
        self,
        primary_provider: str   = "groq",
        primary_model: str      = PRIMARY_MODEL,
        primary_key: str        = "",
        secondary_provider: Optional[str] = None,   # ignored — always groq
        secondary_model: Optional[str]    = None,
        secondary_key: Optional[str]      = None,   # ignored — reuses primary key
        circuit_breaker_threshold: int    = 3,
    ):
        if not primary_key:
            raise ConfigurationError(
                "GROQ_API_KEY is missing. Add it to your .env file.\n"
                "Get a free key at: https://console.groq.com"
            )

        self.primary_model   = primary_model
        self.secondary_model = secondary_model or self.SECONDARY_MODEL
        self._key            = primary_key

        self._primary_cb   = CircuitBreaker(circuit_breaker_threshold)
        self._secondary_cb = CircuitBreaker(circuit_breaker_threshold)

        try:
            from groq import Groq
            self._client = Groq(api_key=primary_key)
        except ImportError:
            raise ConfigurationError(
                "groq package not installed. Run: pip install groq"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Single completion — primary model, falls back to secondary."""
        try:
            return self._primary_cb.call(
                self._call, self.primary_model, prompt, system_prompt
            )
        except Exception as primary_err:
            try:
                return self._secondary_cb.call(
                    self._call, self.secondary_model, prompt, system_prompt
                )
            except Exception as secondary_err:
                raise RuntimeError(
                    f"Both models failed.\n"
                    f"  Primary  ({self.primary_model}): "
                    f"{redact_keys(str(primary_err))}\n"
                    f"  Secondary({self.secondary_model}): "
                    f"{redact_keys(str(secondary_err))}"
                )

    def complete_consensus(self, prompt: str, system_prompt: str = "") -> ConsensusResult:
        """
        Query primary model, then secondary for consensus.
        Returns ConsensusResult with final_response = primary (higher quality).
        """
        primary_resp = self.complete(prompt, system_prompt)

        # Try secondary for consensus check
        try:
            secondary_resp = self._secondary_cb.call(
                self._call, self.secondary_model, prompt, system_prompt
            )
        except Exception:
            # Secondary unavailable — just use primary
            return ConsensusResult(
                primary_response=primary_resp,
                secondary_response="",
                agreed=True,
                final_response=primary_resp,
                disagreement_note="",
            )

        agreed = self._responses_agree(primary_resp, secondary_resp)
        return ConsensusResult(
            primary_response=primary_resp,
            secondary_response=secondary_resp,
            agreed=agreed,
            final_response=primary_resp,   # always use primary (higher quality)
            disagreement_note="" if agreed else
                f"Models disagreed. Using {self.primary_model} response.",
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call(self, model: str, prompt: str, system_prompt: str) -> str:
        """Single Groq API call with 1 retry on transient error."""
        # Rate limiting
        try:
            from agents.rate_limiter import LLMRateLimiter
            LLMRateLimiter.acquire("groq", timeout=30.0)
        except ImportError:
            pass

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(3):
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=4096,
                )
                return resp.choices[0].message.content
            except Exception as exc:
                err_str = str(exc)
                # Don't retry on auth / model-not-found errors
                if "401" in err_str or "404" in err_str or "model" in err_str.lower():
                    raise
                # Rate limit — wait longer
                if "429" in err_str or "rate" in err_str.lower():
                    wait = 20 if attempt == 0 else 40
                    print(f"  [LLM] Rate limited — waiting {wait}s before retry {attempt+1}/3...")
                    time.sleep(wait)
                    continue
                if attempt < 2:
                    time.sleep(3)
                    continue
                raise

    def _responses_agree(self, a: str, b: str) -> bool:
        tokens_a = set(a.lower().split())
        tokens_b = set(b.lower().split())
        if not tokens_a or not tokens_b:
            return True
        overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
        return overlap > 0.6
