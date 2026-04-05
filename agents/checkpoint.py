"""
agents/checkpoint.py — Fernet-encrypted state checkpointing.
Saves and restores full run state so crashes don't lose progress.
"""
from __future__ import annotations

import base64
import json
import os
import pickle
from pathlib import Path
from typing import Optional

from agents.models import CheckpointState
from agents.security import derive_session_key


def _get_fernet(session_key: bytes):
    from cryptography.fernet import Fernet
    # Fernet requires a 32-byte URL-safe base64-encoded key
    key_b64 = base64.urlsafe_b64encode(session_key[:32])
    return Fernet(key_b64)


class CheckpointManager:
    """
    Saves CheckpointState to disk as Fernet-encrypted pickle files.
    Filename: {checkpoint_dir}/{session_token}_cycle{N}.ckpt
    """

    def __init__(self, checkpoint_dir: str, session_key: bytes):
        self._dir = Path(checkpoint_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._key = session_key

    def save(self, state: CheckpointState) -> None:
        path = self._path(state.session_token, state.cycle_num)
        raw = pickle.dumps(state)
        encrypted = _get_fernet(self._key).encrypt(raw)
        path.write_bytes(encrypted)

    def load(self, session_token: str) -> Optional[CheckpointState]:
        """Load the latest checkpoint for a session token."""
        candidates = sorted(
            self._dir.glob(f"{session_token}_cycle*.ckpt"),
            key=lambda p: int(p.stem.split("cycle")[-1]),
            reverse=True,
        )
        for path in candidates:
            try:
                encrypted = path.read_bytes()
                raw = _get_fernet(self._key).decrypt(encrypted)
                return pickle.loads(raw)
            except Exception:
                continue
        return None

    def _path(self, session_token: str, cycle_num: int) -> Path:
        return self._dir / f"{session_token}_cycle{cycle_num}.ckpt"
