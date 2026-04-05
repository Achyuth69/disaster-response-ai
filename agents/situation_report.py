"""
agents/situation_report.py — Automated Situation Report Generator.

Generates professional situation reports using the LLM:
- Government SITREP format
- Press briefing
- Social media posts (Twitter/X, WhatsApp)
- Internal command briefing

These are the actual documents that go to:
- Chief Minister's office
- NDMA headquarters
- Media
- Field commanders
"""
from __future__ import annotations
from datetime import datetime


SITREP_PROMPT = """You are a senior disaster management officer writing an official situation report.

DISASTER CONTEXT:
Type: {disaster_type}
Location: {location}
Severity: {severity}/10
Time Elapsed: {time_elapsed}h
Cycles Completed: {cycles}

OPERATIONAL DATA:
- Zones affected: {zones}
- Total population at risk: {population:,}
- Lives saved so far: {lives_saved:,}
- Resources remaining: Teams={teams}, Boats={boats}, Medical={medical}
- Latest chaos event: {chaos_event}
- Avg agent confidence: {confidence:.0%}

Generate a professional situation report with these sections:
1. EXECUTIVE SUMMARY (2-3 sentences for senior officials)
2. CURRENT SITUATION (what is happening right now)
3. RESPONSE ACTIONS TAKEN (what has been done)
4. PRIORITY ZONES (top 3 with status)
5. RESOURCE STATUS (what's available vs needed)
6. IMMEDIATE REQUIREMENTS (what is needed in next 2 hours)
7. NEXT 6-HOUR OUTLOOK (what to expect)

Format: Professional government document. Be specific with numbers. No fluff."""

PRESS_PROMPT = """You are a government spokesperson writing a press briefing for media.

DISASTER: {disaster_type} in {location} (Severity {severity}/10)
Time: {time_elapsed}h since onset
Lives saved: {lives_saved:,}
Population affected: {population:,}
Latest update: {chaos_event}

Write a 150-word press briefing that:
- Is calm and reassuring
- States facts clearly
- Gives specific evacuation instructions
- Mentions emergency numbers (100 Police, 108 Ambulance, 101 Fire)
- Ends with what government is doing

No panic language. Professional tone."""

SOCIAL_PROMPT = """Write 3 social media posts for disaster response:

Disaster: {disaster_type} in {location}
Key message: {lives_saved:,} lives saved, operations ongoing

Post 1 (Twitter/X - max 280 chars): Urgent update with hashtags
Post 2 (WhatsApp - conversational): For community groups
Post 3 (Facebook - detailed): For official page

Include: Emergency numbers, evacuation routes, shelter locations
Hashtags: #DisasterResponse #{location} #NDRF #EmergencyAlert"""


def generate_sitrep(llm_client, context: dict) -> dict:
    """Generate all situation report formats using LLM."""
    results = {}

    # SITREP
    try:
        sitrep_prompt = SITREP_PROMPT.format(**context)
        results["sitrep"] = llm_client.complete(sitrep_prompt,
            "You are a senior disaster management officer. Write formal, precise reports.")
    except Exception as e:
        results["sitrep"] = f"[Generation failed: {e.__class__.__name__}]"

    # Press briefing
    try:
        press_prompt = PRESS_PROMPT.format(**context)
        results["press_briefing"] = llm_client.complete(press_prompt,
            "You are a government spokesperson. Write calm, factual press briefings.")
    except Exception as e:
        results["press_briefing"] = f"[Generation failed: {e.__class__.__name__}]"

    # Social media
    try:
        social_prompt = SOCIAL_PROMPT.format(**context)
        results["social_media"] = llm_client.complete(social_prompt,
            "You write social media posts for government disaster response accounts.")
    except Exception as e:
        results["social_media"] = f"[Generation failed: {e.__class__.__name__}]"

    results["generated_at"] = datetime.utcnow().isoformat()
    return results
