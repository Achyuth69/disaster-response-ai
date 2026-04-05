"""
agents/volunteer_coordinator.py — AI volunteer skill matching.
Real-time matching of volunteer skills to disaster tasks.
World-first: AI-powered volunteer deployment optimization.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Volunteer:
    volunteer_id: str
    name: str
    skills: list[str]
    location: str
    availability: str       # "IMMEDIATE" | "1HR" | "2HR" | "4HR"
    languages: list[str]
    assigned_task: Optional[str]
    assigned_zone: Optional[str]
    match_score: float
    contact: str
    organization: str


@dataclass
class VolunteerTask:
    task_id: str
    task_name: str
    zone: str
    required_skills: list[str]
    urgency: str
    volunteers_needed: int
    volunteers_assigned: int
    description: str


def run_volunteer_coordinator(
    session_token: str,
    location: str,
    disaster_type: str,
    severity: int,
    zones: list[dict],
) -> dict:
    """Match available volunteers to disaster tasks using AI skill matching."""

    # Volunteer pool (simulated registered volunteers)
    VOLUNTEER_POOL = [
        ("Ravi Kumar", ["first_aid", "rescue", "swimming"], "IMMEDIATE", ["Telugu", "Hindi"], "NDRF"),
        ("Priya Sharma", ["medical", "nursing", "triage"], "IMMEDIATE", ["Telugu", "English"], "Red Cross"),
        ("Mohammed Ali", ["logistics", "driving", "coordination"], "1HR", ["Telugu", "Urdu"], "Civil Defense"),
        ("Sunita Reddy", ["counseling", "social_work", "child_care"], "IMMEDIATE", ["Telugu", "Hindi"], "NGO"),
        ("Arjun Patel", ["engineering", "construction", "rescue"], "2HR", ["Hindi", "English"], "NDRF"),
        ("Lakshmi Devi", ["cooking", "nutrition", "distribution"], "IMMEDIATE", ["Telugu"], "Anganwadi"),
        ("Venkat Rao", ["communication", "radio", "IT"], "1HR", ["Telugu", "English"], "HAM Radio"),
        ("Fatima Begum", ["medical", "midwifery", "child_care"], "IMMEDIATE", ["Telugu", "Urdu"], "Health Dept"),
        ("Suresh Babu", ["boat_operation", "swimming", "rescue"], "IMMEDIATE", ["Telugu"], "Fishermen Assoc"),
        ("Ananya Singh", ["psychology", "counseling", "trauma"], "1HR", ["Hindi", "English"], "NIMHANS"),
        ("Kiran Kumar", ["search_rescue", "rope_work", "first_aid"], "IMMEDIATE", ["Telugu"], "Mountain Rescue"),
        ("Deepa Nair", ["nursing", "medical", "triage"], "2HR", ["Malayalam", "English"], "Red Cross"),
        ("Ramesh Yadav", ["driving", "logistics", "heavy_vehicle"], "1HR", ["Hindi", "Telugu"], "Transport Dept"),
        ("Meera Krishnan", ["social_work", "coordination", "languages"], "IMMEDIATE", ["Tamil", "Telugu", "English"], "NGO"),
        ("Anil Gupta", ["IT", "communication", "data_entry"], "1HR", ["Hindi", "English"], "Tech Volunteers"),
    ]

    # Task requirements by disaster type
    TASK_TEMPLATES = {
        "flood": [
            ("Water Rescue Operations", ["swimming", "boat_operation", "rescue"], "CRITICAL", 5),
            ("Medical Triage at Camps", ["medical", "triage", "nursing"], "CRITICAL", 8),
            ("Food Distribution", ["cooking", "distribution", "logistics"], "HIGH", 6),
            ("Psychological Support", ["counseling", "psychology", "social_work"], "HIGH", 4),
            ("Communication Hub", ["communication", "IT", "radio"], "HIGH", 3),
            ("Child & Elderly Care", ["child_care", "social_work", "nursing"], "MODERATE", 5),
            ("Logistics Coordination", ["logistics", "driving", "coordination"], "MODERATE", 4),
            ("Search & Rescue", ["search_rescue", "rope_work", "first_aid"], "CRITICAL", 6),
        ],
        "earthquake": [
            ("Rubble Search & Rescue", ["search_rescue", "engineering", "rope_work"], "CRITICAL", 10),
            ("Medical Emergency Care", ["medical", "triage", "nursing"], "CRITICAL", 8),
            ("Structural Assessment", ["engineering", "construction"], "HIGH", 4),
            ("Trauma Counseling", ["psychology", "counseling", "trauma"], "HIGH", 6),
            ("Supply Distribution", ["logistics", "driving", "distribution"], "HIGH", 5),
        ],
    }

    tasks_template = TASK_TEMPLATES.get(disaster_type, TASK_TEMPLATES["flood"])

    # Create tasks for each zone
    all_tasks = []
    for i, zone in enumerate(zones[:4]):  # top 4 zones
        zone_name = zone.get("name", f"Zone {i+1}")
        for j, (task_name, skills, urgency, needed) in enumerate(tasks_template[:4]):
            task = VolunteerTask(
                task_id=f"T{i}{j:02d}",
                task_name=task_name,
                zone=zone_name,
                required_skills=skills,
                urgency=urgency,
                volunteers_needed=needed,
                volunteers_assigned=0,
                description=f"{task_name} at {zone_name}",
            )
            all_tasks.append(task)

    # Match volunteers to tasks using skill scoring
    matched_volunteers = []
    task_assignments = {t.task_id: [] for t in all_tasks}

    for i, (name, skills, avail, langs, org) in enumerate(VOLUNTEER_POOL):
        best_task = None
        best_score = 0.0

        for task in all_tasks:
            if task.volunteers_assigned >= task.volunteers_needed:
                continue
            # Skill match score
            matching = set(skills) & set(task.required_skills)
            score = len(matching) / max(1, len(task.required_skills))
            # Urgency bonus
            if task.urgency == "CRITICAL":
                score *= 1.5
            elif task.urgency == "HIGH":
                score *= 1.2
            # Availability penalty
            if avail == "2HR":
                score *= 0.8
            elif avail == "4HR":
                score *= 0.6

            if score > best_score:
                best_score = score
                best_task = task

        vol = Volunteer(
            volunteer_id=f"V{i:03d}",
            name=name,
            skills=skills,
            location=location,
            availability=avail,
            languages=langs,
            assigned_task=best_task.task_name if best_task else None,
            assigned_zone=best_task.zone if best_task else None,
            match_score=round(best_score, 3),
            contact=f"+91-{random.randint(7000000000, 9999999999)}",
            organization=org,
        )
        matched_volunteers.append(vol)

        if best_task:
            best_task.volunteers_assigned += 1
            task_assignments[best_task.task_id].append(vol.volunteer_id)

    # Stats
    assigned = sum(1 for v in matched_volunteers if v.assigned_task)
    unassigned = len(matched_volunteers) - assigned
    coverage = sum(
        min(1.0, t.volunteers_assigned / t.volunteers_needed)
        for t in all_tasks
    ) / max(1, len(all_tasks))

    critical_tasks_covered = sum(
        1 for t in all_tasks
        if t.urgency == "CRITICAL" and t.volunteers_assigned >= t.volunteers_needed
    )
    critical_tasks_total = sum(1 for t in all_tasks if t.urgency == "CRITICAL")

    return {
        "session_token": session_token,
        "computed_at": datetime.utcnow().isoformat(),
        "location": location,
        "disaster_type": disaster_type,
        "summary": {
            "total_volunteers": len(matched_volunteers),
            "assigned": assigned,
            "unassigned": unassigned,
            "total_tasks": len(all_tasks),
            "coverage_pct": round(coverage * 100, 1),
            "critical_tasks_covered": critical_tasks_covered,
            "critical_tasks_total": critical_tasks_total,
            "avg_match_score": round(sum(v.match_score for v in matched_volunteers) / max(1, len(matched_volunteers)), 2),
        },
        "volunteers": [
            {
                "volunteer_id": v.volunteer_id,
                "name": v.name,
                "skills": v.skills,
                "availability": v.availability,
                "languages": v.languages,
                "assigned_task": v.assigned_task,
                "assigned_zone": v.assigned_zone,
                "match_score": v.match_score,
                "contact": v.contact,
                "organization": v.organization,
                "status_color": "#00ff88" if v.assigned_task else "#ff6600",
            }
            for v in matched_volunteers
        ],
        "tasks": [
            {
                "task_id": t.task_id,
                "task_name": t.task_name,
                "zone": t.zone,
                "required_skills": t.required_skills,
                "urgency": t.urgency,
                "needed": t.volunteers_needed,
                "assigned": t.volunteers_assigned,
                "gap": max(0, t.volunteers_needed - t.volunteers_assigned),
                "coverage_pct": round(t.volunteers_assigned / t.volunteers_needed * 100),
                "color": (
                    "#ff2020" if t.urgency == "CRITICAL" and t.volunteers_assigned < t.volunteers_needed else
                    "#ff6600" if t.urgency == "HIGH" else "#00ff88"
                ),
            }
            for t in all_tasks
        ],
        "skill_gaps": [
            skill for task in all_tasks
            if task.volunteers_assigned < task.volunteers_needed
            for skill in task.required_skills
        ][:10],
    }
