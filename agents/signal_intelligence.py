"""
agents/signal_intelligence.py — Survivor Signal Intelligence.

Simulates processing emergency signals (social media, SMS, calls)
to extract survivor locations, injury severity, and resource needs.
Creates rescue tickets automatically.

In production: would connect to Twitter/X API, Twilio SMS,
emergency call centers, and WhatsApp Business API.
For demo: generates realistic synthetic signals based on
actual zone data and disaster context.
"""
from __future__ import annotations
import random
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class SurvivorSignal:
    signal_id: str
    source: str          # "sms" | "social_media" | "emergency_call" | "whatsapp"
    raw_text: str
    extracted_location: str
    lat: float
    lon: float
    severity: str        # "critical" | "urgent" | "moderate" | "minor"
    people_count: int
    needs: list[str]     # ["medical", "rescue", "food", "water", "shelter"]
    timestamp: str
    confidence: float    # 0-1 (AI extraction confidence)
    rescue_ticket_id: str
    status: str = "open"  # "open" | "assigned" | "resolved"


# Realistic signal templates
SMS_TEMPLATES = [
    ("critical", "HELP! {n} people trapped on rooftop {loc}. Water rising fast. Need boats URGENT!",
     ["rescue", "medical"]),
    ("critical", "Building collapsed {loc}. {n} people under rubble. Send ambulance NOW",
     ["rescue", "medical"]),
    ("urgent", "{n} elderly people stranded {loc}. No food water since {h} hours. Please help",
     ["rescue", "food", "water", "medical"]),
    ("urgent", "Pregnant woman needs immediate evacuation {loc}. {n} others also need help",
     ["rescue", "medical"]),
    ("moderate", "{n} families at {loc} need food and water. Roads blocked. Can walk to pickup point",
     ["food", "water"]),
    ("moderate", "Diabetic patient {loc} ran out of insulin. {n} people need medicines",
     ["medical"]),
    ("minor", "{n} people at {loc} need shelter. House flooded but everyone safe",
     ["shelter"]),
]

SOCIAL_TEMPLATES = [
    ("critical", "EMERGENCY: {n} people trapped {loc} #FloodRelief #SOS #Hyderabad",
     ["rescue"]),
    ("urgent", "My family of {n} stuck at {loc} since {h}hrs. No rescue yet. Please RT #HelpNeeded",
     ["rescue", "food"]),
    ("moderate", "Relief camp at {loc} running out of food for {n} people. Need supplies #DisasterRelief",
     ["food", "water"]),
]

CALL_TEMPLATES = [
    ("critical", "Caller reports {n} people trapped in flooded building at {loc}. Caller is injured.",
     ["rescue", "medical"]),
    ("urgent", "Caller requesting evacuation for {n} elderly residents at {loc}. No mobility.",
     ["rescue", "medical"]),
    ("moderate", "Caller reports {n} people need food and water at {loc}. Situation stable.",
     ["food", "water"]),
]


def generate_signals(
    zones: list[dict],
    disaster_type: str,
    severity: int,
    time_elapsed_hours: float,
    num_signals: int = 15,
) -> list[SurvivorSignal]:
    """Generate realistic survivor signals based on zone data."""
    signals = []
    sev = severity / 10.0

    for i in range(num_signals):
        # Pick a zone
        zone = zones[i % len(zones)] if zones else {"name": "Unknown Zone", "lat": 17.38, "lon": 78.47}
        zone_name = zone.get("name", "Unknown")
        base_lat = zone.get("lat", 17.38)
        base_lon = zone.get("lon", 78.47)

        # Add small random offset for realism
        h = int(hashlib.md5(f"{zone_name}{i}".encode()).hexdigest(), 16)
        lat = base_lat + ((h % 200) - 100) / 10000
        lon = base_lon + ((h % 300) - 150) / 10000

        # Pick source and template
        source_roll = (h >> 4) % 10
        if source_roll < 4:
            source = "sms"
            templates = SMS_TEMPLATES
        elif source_roll < 7:
            source = "social_media"
            templates = SOCIAL_TEMPLATES
        else:
            source = "emergency_call"
            templates = CALL_TEMPLATES

        tmpl_idx = (h >> 8) % len(templates)
        severity_str, text_tmpl, needs = templates[tmpl_idx]

        # Fill template
        n_people = max(1, int(zone.get("population_at_risk", 1000) * 0.001 * sev) + (h % 20))
        hours_str = str(int(time_elapsed_hours))
        text = text_tmpl.format(n=n_people, loc=zone_name, h=hours_str)

        # Timestamp (spread over last few hours)
        mins_ago = (h % int(time_elapsed_hours * 60 + 1))
        ts = (datetime.utcnow() - timedelta(minutes=mins_ago)).strftime("%H:%M:%S UTC")

        # Confidence based on source
        conf = {"sms": 0.85, "social_media": 0.65, "emergency_call": 0.95}.get(source, 0.75)

        signal_id = f"SIG-{i+1:04d}"
        ticket_id = f"TKT-{hashlib.md5(signal_id.encode()).hexdigest()[:6].upper()}"

        signals.append(SurvivorSignal(
            signal_id=signal_id,
            source=source,
            raw_text=text,
            extracted_location=zone_name,
            lat=lat, lon=lon,
            severity=severity_str,
            people_count=n_people,
            needs=needs,
            timestamp=ts,
            confidence=conf,
            rescue_ticket_id=ticket_id,
            status="open" if severity_str in ("critical", "urgent") else "assigned",
        ))

    # Sort by severity
    order = {"critical": 0, "urgent": 1, "moderate": 2, "minor": 3}
    signals.sort(key=lambda s: order.get(s.severity, 4))
    return signals
