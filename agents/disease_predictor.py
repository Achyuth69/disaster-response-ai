"""
agents/disease_predictor.py — Post-Disaster Disease Outbreak Predictor.

Predicts disease outbreaks that follow disasters:
- Flood → Cholera, Leptospirosis, Typhoid, Dengue, Malaria
- Earthquake → Tetanus, Crush syndrome, Respiratory infections
- Cyclone → Diarrheal diseases, Respiratory infections
- Wildfire → Respiratory diseases, Burns infections

Based on WHO post-disaster disease surveillance guidelines.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class DiseaseRisk:
    disease: str
    risk_level: str      # "low" | "medium" | "high" | "critical"
    risk_score: float    # 0-1
    onset_days: float    # days after disaster when outbreak likely
    peak_days: float     # days to peak
    affected_estimate: int
    prevention: list[str]
    symptoms: str
    color: str


DISEASE_PROFILES = {
    "flood": [
        {
            "disease": "Cholera", "base_risk": 0.7,
            "onset_days": 3, "peak_days": 14,
            "prevention": ["Boil water before drinking", "ORS distribution", "Chlorination of water sources"],
            "symptoms": "Severe watery diarrhea, vomiting, dehydration",
        },
        {
            "disease": "Leptospirosis", "base_risk": 0.65,
            "onset_days": 5, "peak_days": 21,
            "prevention": ["Avoid wading in floodwater", "Wear rubber boots", "Doxycycline prophylaxis for rescue workers"],
            "symptoms": "High fever, muscle pain, jaundice, kidney failure",
        },
        {
            "disease": "Typhoid", "base_risk": 0.55,
            "onset_days": 7, "peak_days": 28,
            "prevention": ["Safe water supply", "Food hygiene", "Typhoid vaccination"],
            "symptoms": "Sustained fever, abdominal pain, rose spots",
        },
        {
            "disease": "Dengue", "base_risk": 0.6,
            "onset_days": 10, "peak_days": 35,
            "prevention": ["Eliminate stagnant water", "Mosquito nets", "Fogging operations"],
            "symptoms": "High fever, severe headache, joint pain, rash",
        },
        {
            "disease": "Malaria", "base_risk": 0.5,
            "onset_days": 14, "peak_days": 42,
            "prevention": ["Indoor residual spraying", "Bed nets", "Antimalarial prophylaxis"],
            "symptoms": "Cyclical fever, chills, sweating, anemia",
        },
        {
            "disease": "Acute Diarrheal Disease", "base_risk": 0.8,
            "onset_days": 2, "peak_days": 10,
            "prevention": ["Hand washing with soap", "Safe food handling", "ORS availability"],
            "symptoms": "Diarrhea, vomiting, dehydration",
        },
    ],
    "earthquake": [
        {
            "disease": "Tetanus", "base_risk": 0.6,
            "onset_days": 3, "peak_days": 14,
            "prevention": ["Tetanus vaccination", "Wound cleaning", "Antibiotic prophylaxis"],
            "symptoms": "Muscle stiffness, lockjaw, spasms",
        },
        {
            "disease": "Crush Syndrome / Renal Failure", "base_risk": 0.7,
            "onset_days": 1, "peak_days": 5,
            "prevention": ["Rapid rescue", "IV fluid resuscitation", "Dialysis availability"],
            "symptoms": "Dark urine, muscle pain, kidney failure",
        },
        {
            "disease": "Respiratory Infections", "base_risk": 0.65,
            "onset_days": 5, "peak_days": 21,
            "prevention": ["Dust masks", "Shelter from elements", "Antibiotics"],
            "symptoms": "Cough, fever, breathing difficulty",
        },
    ],
    "cyclone": [
        {
            "disease": "Acute Respiratory Infections", "base_risk": 0.7,
            "onset_days": 3, "peak_days": 14,
            "prevention": ["Shelter", "Warm clothing", "Antibiotics"],
            "symptoms": "Cough, fever, pneumonia",
        },
        {
            "disease": "Diarrheal Diseases", "base_risk": 0.65,
            "onset_days": 2, "peak_days": 10,
            "prevention": ["Safe water", "Food hygiene", "ORS"],
            "symptoms": "Diarrhea, vomiting, dehydration",
        },
    ],
    "wildfire": [
        {
            "disease": "Smoke Inhalation / COPD", "base_risk": 0.85,
            "onset_days": 1, "peak_days": 7,
            "prevention": ["N95 masks", "Evacuation from smoke zones", "Bronchodilators"],
            "symptoms": "Coughing, wheezing, chest pain, eye irritation",
        },
        {
            "disease": "Burn Wound Infections", "base_risk": 0.6,
            "onset_days": 2, "peak_days": 14,
            "prevention": ["Wound care", "Antibiotics", "Burn unit capacity"],
            "symptoms": "Infected burns, fever, sepsis",
        },
    ],
}


def predict_disease_outbreaks(
    disaster_type: str,
    severity: int,
    total_population: int,
    time_elapsed_hours: float,
    sanitation_compromised: bool = True,
    water_contaminated: bool = True,
) -> list[DiseaseRisk]:
    """Predict disease outbreak risks post-disaster."""
    sev = severity / 10.0
    profiles = DISEASE_PROFILES.get(disaster_type, DISEASE_PROFILES["flood"])
    risks = []

    for p in profiles:
        # Risk amplifiers
        risk = p["base_risk"] * sev
        if sanitation_compromised:
            risk = min(1.0, risk * 1.3)
        if water_contaminated and p["disease"] in ("Cholera", "Typhoid", "Acute Diarrheal Disease"):
            risk = min(1.0, risk * 1.4)

        # Time factor: risk increases as time passes without intervention
        time_factor = 1 + (time_elapsed_hours / 24) * 0.1
        risk = min(1.0, risk * time_factor)

        # Affected estimate
        affected = int(total_population * risk * 0.05)

        # Risk level
        if risk > 0.75:
            level = "critical"
            color = "#ff2020"
        elif risk > 0.55:
            level = "high"
            color = "#ff6600"
        elif risk > 0.35:
            level = "medium"
            color = "#ffcc00"
        else:
            level = "low"
            color = "#00ff88"

        risks.append(DiseaseRisk(
            disease=p["disease"],
            risk_level=level,
            risk_score=round(risk, 3),
            onset_days=p["onset_days"],
            peak_days=p["peak_days"],
            affected_estimate=affected,
            prevention=p["prevention"],
            symptoms=p["symptoms"],
            color=color,
        ))

    risks.sort(key=lambda r: r.risk_score, reverse=True)
    return risks
