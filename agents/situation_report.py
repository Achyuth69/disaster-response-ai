"""
agents/situation_report.py — Automated Situation Report Generator.

Generates SITREP, press briefing, and social media posts in ONE LLM call
to stay within Railway/Render's 60-second HTTP timeout.
"""
from __future__ import annotations
from datetime import datetime


COMBINED_PROMPT = """You are a senior disaster management officer. Generate ALL THREE reports below in ONE response.

DISASTER CONTEXT:
Type: {disaster_type}
Location: {location}
Severity: {severity}/10
Time Elapsed: {time_elapsed}h
Cycles: {cycles}
Zones: {zones}
Population at risk: {population:,}
Lives saved: {lives_saved:,}
Resources: Teams={teams}, Boats={boats}, Medical={medical}
Latest event: {chaos_event}
Confidence: {confidence:.0%}

---REPORT 1: SITREP---
Write a government situation report with:
1. EXECUTIVE SUMMARY (2 sentences)
2. CURRENT SITUATION
3. RESPONSE ACTIONS TAKEN
4. PRIORITY ZONES (top 3)
5. RESOURCE STATUS
6. IMMEDIATE REQUIREMENTS (next 2 hours)
7. NEXT 6-HOUR OUTLOOK

---REPORT 2: PRESS BRIEFING---
Write a 120-word calm press briefing. Include emergency numbers: Police 100, Ambulance 108, Fire 101.

---REPORT 3: SOCIAL MEDIA---
Write 3 posts:
[TWITTER] Max 280 chars with hashtags #DisasterResponse #{location} #NDRF
[WHATSAPP] Conversational message for community groups
[FACEBOOK] Detailed post for official page

Keep each section clearly separated with the headers shown above."""


def generate_sitrep(llm_client, context: dict) -> dict:
    """
    Generate all situation report formats in a SINGLE LLM call.
    This keeps total time under 25 seconds, well within Railway's 60s timeout.
    """
    results = {}

    try:
        prompt = COMBINED_PROMPT.format(**context)
        raw = llm_client.complete(
            prompt,
            "You are a senior disaster management officer. Generate all three reports clearly separated."
        )

        # Parse the three sections from the combined response
        sitrep_part = ""
        press_part = ""
        social_part = ""

        # Split by section headers
        if "---REPORT 2: PRESS BRIEFING---" in raw:
            parts = raw.split("---REPORT 2: PRESS BRIEFING---")
            sitrep_part = parts[0].replace("---REPORT 1: SITREP---", "").strip()
            rest = parts[1] if len(parts) > 1 else ""
            if "---REPORT 3: SOCIAL MEDIA---" in rest:
                press_social = rest.split("---REPORT 3: SOCIAL MEDIA---")
                press_part = press_social[0].strip()
                social_part = press_social[1].strip() if len(press_social) > 1 else ""
            else:
                press_part = rest.strip()
        else:
            # Fallback: use entire response as SITREP
            sitrep_part = raw.strip()

        # Parse social media sub-sections
        twitter = ""
        whatsapp = ""
        facebook = ""
        if social_part:
            if "[TWITTER]" in social_part:
                parts = social_part.split("[TWITTER]")
                after_twitter = parts[1] if len(parts) > 1 else ""
                if "[WHATSAPP]" in after_twitter:
                    tw_wa = after_twitter.split("[WHATSAPP]")
                    twitter = tw_wa[0].strip()
                    after_wa = tw_wa[1] if len(tw_wa) > 1 else ""
                    if "[FACEBOOK]" in after_wa:
                        wa_fb = after_wa.split("[FACEBOOK]")
                        whatsapp = wa_fb[0].strip()
                        facebook = wa_fb[1].strip() if len(wa_fb) > 1 else ""
                    else:
                        whatsapp = after_wa.strip()
                else:
                    twitter = after_twitter.strip()

        results["sitrep"] = sitrep_part or raw
        results["press_briefing"] = press_part or f"Emergency operations ongoing in {context.get('location','the affected area')}. {context.get('lives_saved',0):,} lives saved. Call 100 (Police), 108 (Ambulance), 101 (Fire) for emergencies."
        results["social_media"] = social_part or f"🚨 {context.get('disaster_type','DISASTER').upper()} ALERT — {context.get('location','')} | {context.get('lives_saved',0):,} lives saved | Operations ongoing #DisasterResponse #{context.get('location','').replace(' ','')} #NDRF"
        results["twitter"] = twitter
        results["whatsapp"] = whatsapp
        results["facebook"] = facebook

    except Exception as e:
        # Fallback: generate a basic SITREP without LLM
        ctx = context
        results["sitrep"] = _fallback_sitrep(ctx)
        results["press_briefing"] = _fallback_press(ctx)
        results["social_media"] = _fallback_social(ctx)
        results["error"] = f"LLM unavailable ({e.__class__.__name__}) — using template report"

    results["generated_at"] = datetime.utcnow().isoformat()
    return results


def _fallback_sitrep(ctx: dict) -> str:
    """Template-based SITREP when LLM is unavailable."""
    return f"""SITUATION REPORT — {ctx.get('disaster_type','DISASTER').upper()} RESPONSE
Location: {ctx.get('location','Unknown')} | Severity: {ctx.get('severity',8)}/10
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC

1. EXECUTIVE SUMMARY
A severity {ctx.get('severity',8)}/10 {ctx.get('disaster_type','disaster')} is ongoing in {ctx.get('location','the affected area')}. {ctx.get('lives_saved',0):,} lives have been saved across {ctx.get('cycles',0)} response cycles.

2. CURRENT SITUATION
Disaster type: {ctx.get('disaster_type','Unknown').upper()}
Zones affected: {ctx.get('zones','Multiple zones')}
Population at risk: {ctx.get('population',0):,}
Time elapsed: {ctx.get('time_elapsed',0)}h

3. RESPONSE ACTIONS TAKEN
- {ctx.get('teams',0)} rescue teams deployed
- {ctx.get('boats',0)} boats operational
- {ctx.get('medical',0)} medical kits distributed
- {ctx.get('cycles',0)} operational cycles completed

4. RESOURCE STATUS
Teams: {ctx.get('teams',0)} | Boats: {ctx.get('boats',0)} | Medical: {ctx.get('medical',0)}

5. IMMEDIATE REQUIREMENTS
Continue rescue operations. Monitor water levels. Maintain supply chain.

6. NEXT 6-HOUR OUTLOOK
Continue current response posture. Reassess resource needs after next cycle."""


def _fallback_press(ctx: dict) -> str:
    return f"""PRESS BRIEFING — {datetime.utcnow().strftime('%d %B %Y, %H:%M')} UTC

The government is responding to a {ctx.get('disaster_type','disaster')} in {ctx.get('location','the affected area')}. {ctx.get('lives_saved',0):,} people have been rescued. Operations are ongoing with {ctx.get('teams',0)} rescue teams deployed.

Residents in affected areas should follow official evacuation instructions. Emergency numbers: Police 100 | Ambulance 108 | Fire 101 | NDRF 011-24363260.

The government is committed to protecting every life."""


def _fallback_social(ctx: dict) -> str:
    loc = ctx.get('location', 'Affected Area')
    lives = ctx.get('lives_saved', 0)
    dis = ctx.get('disaster_type', 'disaster').upper()
    return f"""[TWITTER] 🚨 {dis} ALERT — {loc} | {lives:,} lives saved | Rescue ops ongoing | Emergency: 100/108/101 #DisasterResponse #{loc.replace(' ','')} #NDRF #EmergencyAlert

[WHATSAPP] 🚨 Important Update: {dis} response in {loc} is ongoing. {lives:,} people have been rescued so far. If you need help, call 108 (Ambulance) or 100 (Police). Stay safe and follow official instructions.

[FACEBOOK] 📢 OFFICIAL UPDATE — {dis} Response in {loc}
Our teams have rescued {lives:,} people so far. Operations are continuing 24/7. Emergency contacts: Police 100 | Ambulance 108 | Fire 101. Please share this with anyone in the affected area. #DisasterResponse #StaySafe"""
