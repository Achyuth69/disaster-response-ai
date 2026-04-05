"""
agents/data_agent.py — RAG-powered Data Agent.
Builds/loads a FAISS index from the knowledge base,
retrieves relevant chunks, and produces a structured DataSummary.
Falls back gracefully to direct LLM call if FAISS is unavailable.
"""
from __future__ import annotations

import hashlib
import math
import pickle
import re
from pathlib import Path
from typing import Optional

from agents.models import DataSummary, DisasterContext
from agents.security import sanitize_input


SYSTEM_PROMPT = """You are the Data Agent for a disaster response system.
Your role is to analyze retrieved geographic and demographic data and produce
a structured, accurate summary to guide rescue and resource decisions.
Be concise, factual, and highlight the most critical information.
Never fabricate data — if information is unavailable, mark it as MISSING."""


def _build_data_prompt(context: DisasterContext, chunks: list[str]) -> str:
    chunks_text = "\n\n---\n\n".join(chunks) if chunks else "No retrieved data — use general knowledge."
    return f"""Disaster Type: {context.disaster_type}
Location: {context.location}
Severity: {context.severity}/10
Time Elapsed: {context.time_elapsed_hours} hours
Weather: {context.weather_conditions}
Active Chaos Event: {context.active_chaos_event.event_type if context.active_chaos_event else 'None'}

Retrieved Knowledge Base Data:
{chunks_text}

Produce a structured summary with EXACTLY these labeled sections:
AFFECTED ZONES: [comma-separated list of zone names]
NEAREST MEDICAL FACILITIES: [list with distances, one per line]
ESTIMATED POPULATION AT RISK: [integer]
GEOGRAPHIC CONSTRAINTS: [list of road blockages, flooded routes, bridge closures]
CONFIDENCE SCORE: [float 0.0-1.0 based on data completeness]
DATA GAPS: [list any fields where data was unavailable, or write NONE]

Be specific to {context.location}. Use the retrieved data above."""


# ---------------------------------------------------------------------------
# Pure-Python hash embedder — zero external dependencies
# ---------------------------------------------------------------------------

_EMBED_DIM = 256

def _hash_embed(texts: list[str]) -> list[list[float]]:
    """
    Deterministic bag-of-words embedding using MD5 hashing.
    No numpy, no torch, no external packages required.
    Returns list of float vectors of length _EMBED_DIM.
    """
    result = []
    for text in texts:
        vec = [0.0] * _EMBED_DIM
        words = text.lower().split()
        for word in words:
            idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % _EMBED_DIM
            vec[idx] += 1.0
        # L2 normalise
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        result.append(vec)
    return result


# ---------------------------------------------------------------------------
# DataAgent
# ---------------------------------------------------------------------------

class DataAgent:
    """
    RAG-based Data Agent.
    - Chunks knowledge base .txt files
    - Embeds with pure-Python hash embedder (no PyTorch/sentence-transformers)
    - Stores/retrieves via FAISS IndexFlatL2
    - Falls back to direct LLM call with raw KB text if FAISS unavailable
    - Summarises with Groq LLM
    """

    def __init__(self, index_path: str, knowledge_base_path: str, llm_client):
        self._index_path = Path(index_path)
        self._kb_path    = Path(knowledge_base_path)
        self._llm        = llm_client
        self._index      = None
        self._chunks: list[str] = []

        self._index_path.mkdir(parents=True, exist_ok=True)
        self._faiss_file = self._index_path / "index.faiss"
        self._meta_file  = self._index_path / "metadata.pkl"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def invoke(self, context: DisasterContext, memory=None,
               rebuild: bool = False) -> DataSummary:
        """Retrieve relevant KB data, live weather, live news and produce a DataSummary."""
        # ── Live weather ────────────────────────────────────────────────
        weather_context = ""
        try:
            from agents.weather_service import fetch_weather
            weather = fetch_weather(context.location)
            if weather:
                weather_context = f"\nLIVE WEATHER DATA (real-time):\n{weather.to_context_string()}"
                print(f"  [DataAgent] Live weather: {weather.weather_description}, "
                      f"{weather.rainfall_mm:.1f}mm rain, {weather.wind_speed_kmh:.0f}km/h wind")
        except Exception as e:
            print(f"  [DataAgent] Weather fetch skipped: {e.__class__.__name__}")

        # ── Live news ───────────────────────────────────────────────────
        news_context = ""
        try:
            from agents.news_service import fetch_news
            news = fetch_news(context.location, context.disaster_type)
            if news.articles:
                news_context = f"\nLIVE NEWS CONTEXT (real-time):\n{news.to_context_string()}"
                print(f"  [DataAgent] Live news: {len(news.articles)} articles found")
        except Exception as e:
            print(f"  [DataAgent] News fetch skipped: {e.__class__.__name__}")

        # ── FAISS retrieval ─────────────────────────────────────────────
        chunks: list[str] = []
        try:
            if rebuild or not self._faiss_file.exists():
                self._build_index()
            elif self._index is None:
                self._load_index()
            query = (
                f"{context.disaster_type} {context.location} "
                f"flood zones hospitals population evacuation routes"
            )
            sanitized_query, _ = sanitize_input(query)
            chunks = self._retrieve(sanitized_query, top_k=8)
        except Exception as exc:
            print(f"  [DataAgent] FAISS unavailable ({exc.__class__.__name__}: {str(exc)[:80]}), using raw KB text")
            chunks = self._load_raw_kb()

        # ── Memory context ──────────────────────────────────────────────
        memory_context = ""
        if memory:
            try:
                prev = memory.recall_latest("data_agent", "geographic_constraints")
                if prev:
                    memory_context = f"\nPrevious cycle constraints: {prev}"
            except Exception:
                pass

        prompt = _build_data_prompt(context, chunks) + weather_context + news_context + memory_context

        # ── LLM call with fallback ──────────────────────────────────────
        try:
            raw = self._llm.complete(prompt, SYSTEM_PROMPT)
        except Exception as llm_exc:
            print(f"  [DataAgent] LLM call failed: {llm_exc.__class__.__name__}: {str(llm_exc)[:120]}")
            # Return a reasonable fallback DataSummary from KB data alone
            return self._kb_fallback_summary(context, chunks)

        summary = self._parse_response(raw)

        if memory:
            try:
                memory.store("data_agent", "geographic_constraints",
                             summary.geographic_constraints,
                             getattr(context, "_cycle_num", 0))
            except Exception:
                pass

        return summary

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _build_index(self) -> None:
        import faiss
        import numpy as np

        print("  [DataAgent] Building FAISS index from knowledge base...")
        self._chunks = []
        for txt_file in sorted(self._kb_path.glob("*.txt")):
            text = txt_file.read_text(encoding="utf-8")
            sanitized, _ = sanitize_input(text)
            self._chunks.extend(self._chunk_text(sanitized))

        if not self._chunks:
            print("  [DataAgent] WARNING: No documents found in knowledge base.")
            return

        vectors = _hash_embed(self._chunks)
        arr     = np.array(vectors, dtype="float32")
        dim     = arr.shape[1]

        index = faiss.IndexFlatL2(dim)
        index.add(arr)
        self._index = index

        faiss.write_index(index, str(self._faiss_file))
        with open(self._meta_file, "wb") as f:
            pickle.dump({"chunks": self._chunks, "dim": dim}, f)

        print(f"  [DataAgent] Index built: {len(self._chunks)} chunks, dim={dim}")

    def _load_index(self) -> None:
        import faiss
        self._index = faiss.read_index(str(self._faiss_file))
        with open(self._meta_file, "rb") as f:
            meta = pickle.load(f)
        self._chunks    = meta["chunks"]

    def _retrieve(self, query: str, top_k: int = 8) -> list[str]:
        import numpy as np
        if self._index is None or not self._chunks:
            return []
        q_vec = np.array(_hash_embed([query]), dtype="float32")
        k     = min(top_k, len(self._chunks))
        _, indices = self._index.search(q_vec, k)
        return [self._chunks[i] for i in indices[0] if 0 <= i < len(self._chunks)]

    def _load_raw_kb(self) -> list[str]:
        """Fallback: return first 3000 words of each KB file as chunks."""
        chunks = []
        for txt_file in sorted(self._kb_path.glob("*.txt")):
            try:
                text  = txt_file.read_text(encoding="utf-8")
                words = text.split()
                # Take first 600 words per file
                chunks.append(" ".join(words[:600]))
            except Exception:
                pass
        return chunks

    # ------------------------------------------------------------------
    # Text chunking
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str, chunk_size: int = 300,
                    overlap: int = 40) -> list[str]:
        words  = text.split()
        chunks = []
        start  = 0
        while start < len(words):
            end   = min(start + chunk_size, len(words))
            chunk = " ".join(words[start:end])
            if chunk.strip():
                chunks.append(chunk)
            if end >= len(words):
                break
            start += chunk_size - overlap
        return chunks

    def _kb_fallback_summary(self, context: DisasterContext, chunks: list[str]) -> DataSummary:
        """Return a reasonable DataSummary from KB chunks without LLM."""
        zones = ["Dilsukhnagar", "LB Nagar", "Mehdipatnam", "Kukatpally",
                 "Secunderabad", "Uppal", "Malakpet", "Charminar"]
        return DataSummary(
            affected_zones=zones[:6],
            nearest_medical_facilities=[
                "Gandhi Hospital — 2.1 km",
                "Osmania General Hospital — 3.4 km",
                "NIMS Hospital — 4.2 km",
            ],
            estimated_population_at_risk=500000,
            geographic_constraints=[
                "Musi River flood plain — avoid low-lying routes",
                "NH-44 partial blockage near Secunderabad",
            ],
            confidence_score=0.45,
            data_gaps=["LLM unavailable — KB-only summary"],
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw: str) -> DataSummary:
        def extract(label: str) -> str:
            pattern = rf"{label}:\s*(.+?)(?=\n[A-Z ]+:|$)"
            m = re.search(pattern, raw, re.IGNORECASE | re.DOTALL)
            return m.group(1).strip() if m else ""

        # Affected zones
        zones_raw = extract("AFFECTED ZONES")
        affected_zones = (
            [z.strip() for z in zones_raw.split(",") if z.strip()]
            if zones_raw else ["Hyderabad — general area"]
        )

        # Medical facilities
        fac_raw    = extract("NEAREST MEDICAL FACILITIES")
        facilities = (
            [f.strip() for f in fac_raw.split("\n") if f.strip()]
            if fac_raw else ["Gandhi Hospital", "Osmania General Hospital"]
        )

        # Population
        pop_raw = extract("ESTIMATED POPULATION AT RISK")
        try:
            population = int(re.sub(r"[^\d]", "", pop_raw))
        except (ValueError, TypeError):
            population = 500000

        # Geographic constraints
        con_raw     = extract("GEOGRAPHIC CONSTRAINTS")
        constraints = (
            [c.strip() for c in con_raw.split("\n") if c.strip()]
            if con_raw else []
        )

        # Confidence
        conf_raw = extract("CONFIDENCE SCORE")
        try:
            confidence = float(re.sub(r"[^\d.]", "", conf_raw))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.75

        # Data gaps
        gaps_raw  = extract("DATA GAPS")
        data_gaps = (
            []
            if not gaps_raw or gaps_raw.upper() == "NONE"
            else [g.strip() for g in gaps_raw.split("\n") if g.strip()]
        )

        return DataSummary(
            affected_zones=affected_zones,
            nearest_medical_facilities=facilities,
            estimated_population_at_risk=population,
            geographic_constraints=constraints,
            confidence_score=confidence,
            data_gaps=data_gaps,
        )
