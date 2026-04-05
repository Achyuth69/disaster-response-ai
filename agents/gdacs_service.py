"""
agents/gdacs_service.py — Global Disaster Alert and Coordination System.

Fetches REAL active disasters happening RIGHT NOW worldwide
from GDACS (gdacs.org) — free, no API key needed.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GlobalDisaster:
    event_id: str
    event_type: str       # FL=Flood, EQ=Earthquake, TC=Cyclone, VO=Volcano, DR=Drought, WF=Wildfire
    title: str
    country: str
    severity: str         # Green / Orange / Red
    severity_score: float # 0-3
    lat: float
    lon: float
    date: str
    url: str
    affected: int = 0
    description: str = ""


GDACS_TYPE_MAP = {
    "FL": "flood", "EQ": "earthquake", "TC": "cyclone",
    "VO": "volcano", "DR": "drought", "WF": "wildfire",
    "TS": "tsunami", "LS": "landslide",
}

SEVERITY_COLORS = {
    "Green": "#00ff88", "Orange": "#ff6600", "Red": "#ff2020",
}


def fetch_global_disasters() -> list[GlobalDisaster]:
    """
    Fetch real active disasters from GDACS RSS feed.
    Free, no API key, updated every 30 minutes.
    """
    url = "https://www.gdacs.org/xml/rss.xml"
    disasters = []

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DisasterResponseAI/2.0 (research)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        root = ET.fromstring(content)
        ns = {
            "gdacs": "http://www.gdacs.org",
            "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
            "dc": "http://purl.org/dc/elements/1.1/",
        }

        for item in root.iter("item"):
            try:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                desc = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")

                # GDACS namespace fields
                event_type = item.findtext("gdacs:eventtype", "", ns) or \
                             item.findtext("{http://www.gdacs.org}eventtype", "")
                severity_str = item.findtext("gdacs:alertlevel", "Green", ns) or \
                               item.findtext("{http://www.gdacs.org}alertlevel", "Green")
                country = item.findtext("gdacs:country", "", ns) or \
                          item.findtext("{http://www.gdacs.org}country", "")
                affected_str = item.findtext("gdacs:population", "0", ns) or "0"
                event_id = item.findtext("gdacs:eventid", "", ns) or \
                           item.findtext("{http://www.gdacs.org}eventid", "")

                # Coordinates
                lat_str = item.findtext("geo:lat", "0", ns) or \
                          item.findtext("{http://www.w3.org/2003/01/geo/wgs84_pos#}lat", "0")
                lon_str = item.findtext("geo:long", "0", ns) or \
                          item.findtext("{http://www.w3.org/2003/01/geo/wgs84_pos#}long", "0")

                lat = float(lat_str or 0)
                lon = float(lon_str or 0)

                # Severity score
                sev_map = {"Green": 1.0, "Orange": 2.0, "Red": 3.0}
                sev_score = sev_map.get(severity_str, 1.0)

                # Affected population
                try:
                    affected = int("".join(filter(str.isdigit, affected_str[:10])) or "0")
                except Exception:
                    affected = 0

                if not title or (lat == 0 and lon == 0):
                    continue

                disasters.append(GlobalDisaster(
                    event_id=event_id or f"gdacs_{len(disasters)}",
                    event_type=GDACS_TYPE_MAP.get(event_type, event_type.lower() or "unknown"),
                    title=title,
                    country=country,
                    severity=severity_str,
                    severity_score=sev_score,
                    lat=lat,
                    lon=lon,
                    date=pub_date[:25] if pub_date else "",
                    url=link,
                    affected=affected,
                    description=desc[:200] if desc else "",
                ))
            except Exception:
                continue

    except Exception as exc:
        print(f"  [GDACS] Could not fetch: {exc.__class__.__name__}: {str(exc)[:80]}")
        # Return sample data so UI still works
        disasters = _sample_disasters()

    return disasters[:50]  # cap at 50


def _sample_disasters() -> list[GlobalDisaster]:
    """Fallback sample data when GDACS is unreachable."""
    return [
        GlobalDisaster("eq_001", "earthquake", "M6.2 Earthquake - Turkey", "Turkey",
                       "Orange", 2.0, 38.5, 38.7, "2025-04-05", "", 15000),
        GlobalDisaster("fl_001", "flood", "Severe Flooding - Bangladesh", "Bangladesh",
                       "Red", 3.0, 23.8, 90.4, "2025-04-05", "", 250000),
        GlobalDisaster("tc_001", "cyclone", "Tropical Cyclone - Bay of Bengal", "India",
                       "Orange", 2.0, 15.2, 85.3, "2025-04-05", "", 80000),
        GlobalDisaster("wf_001", "wildfire", "Wildfire - California", "USA",
                       "Orange", 2.0, 34.1, -118.3, "2025-04-05", "", 5000),
        GlobalDisaster("fl_002", "flood", "Flash Floods - Pakistan", "Pakistan",
                       "Red", 3.0, 30.2, 71.5, "2025-04-05", "", 120000),
    ]
