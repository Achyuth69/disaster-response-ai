"""
agents/gdacs_service.py — Global Disaster Intelligence.

Fetches REAL active disasters from multiple free sources:
1. GDACS RSS (gdacs.org) — primary
2. ReliefWeb API (reliefweb.int) — fallback, always works from cloud
3. Static recent data — last resort fallback
"""
from __future__ import annotations
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class GlobalDisaster:
    event_id: str
    event_type: str
    title: str
    country: str
    severity: str         # Green / Orange / Red
    severity_score: float
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


def _fetch_gdacs() -> list[GlobalDisaster]:
    """Try GDACS RSS feed."""
    disasters = []
    try:
        req = urllib.request.Request(
            "https://www.gdacs.org/xml/rss.xml",
            headers={"User-Agent": "DisasterResponseAI/2.0 (research)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        root = ET.fromstring(content)
        ns = {
            "gdacs": "http://www.gdacs.org",
            "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        }

        for item in root.iter("item"):
            try:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                desc = item.findtext("description", "")

                event_type = (item.findtext("gdacs:eventtype", "", ns) or
                              item.findtext("{http://www.gdacs.org}eventtype", ""))
                severity_str = (item.findtext("gdacs:alertlevel", "Green", ns) or
                                item.findtext("{http://www.gdacs.org}alertlevel", "Green") or "Green")
                country = (item.findtext("gdacs:country", "", ns) or
                           item.findtext("{http://www.gdacs.org}country", ""))
                affected_str = item.findtext("gdacs:population", "0", ns) or "0"
                event_id = (item.findtext("gdacs:eventid", "", ns) or
                            item.findtext("{http://www.gdacs.org}eventid", ""))

                lat_str = (item.findtext("geo:lat", "0", ns) or
                           item.findtext("{http://www.w3.org/2003/01/geo/wgs84_pos#}lat", "0"))
                lon_str = (item.findtext("geo:long", "0", ns) or
                           item.findtext("{http://www.w3.org/2003/01/geo/wgs84_pos#}long", "0"))

                lat = float(lat_str or 0)
                lon = float(lon_str or 0)
                if not title or (lat == 0 and lon == 0):
                    continue

                try:
                    affected = int("".join(filter(str.isdigit, affected_str[:10])) or "0")
                except Exception:
                    affected = 0

                sev_map = {"Green": 1.0, "Orange": 2.0, "Red": 3.0}
                disasters.append(GlobalDisaster(
                    event_id=event_id or f"gdacs_{len(disasters)}",
                    event_type=GDACS_TYPE_MAP.get(event_type, event_type.lower() or "unknown"),
                    title=title, country=country,
                    severity=severity_str, severity_score=sev_map.get(severity_str, 1.0),
                    lat=lat, lon=lon,
                    date=pub_date[:25] if pub_date else "",
                    url=link, affected=affected,
                    description=desc[:200] if desc else "",
                ))
            except Exception:
                continue
    except Exception as e:
        print(f"  [GDACS] Primary feed failed: {e.__class__.__name__}: {str(e)[:60]}")

    return disasters


def _fetch_reliefweb() -> list[GlobalDisaster]:
    """
    Fetch from ReliefWeb API — always accessible from cloud servers.
    Free, no API key, returns recent disaster reports.
    """
    disasters = []
    try:
        payload = json.dumps({
            "limit": 20,
            "sort": ["date:desc"],
            "filter": {
                "field": "type.name",
                "value": ["Flood", "Earthquake", "Cyclone", "Tsunami",
                          "Wildfire", "Landslide", "Drought", "Volcano"]
            },
            "fields": {
                "include": ["title", "date", "country", "type",
                            "status", "url", "primary_country"]
            }
        }).encode()

        req = urllib.request.Request(
            "https://api.reliefweb.int/v1/disasters?appname=DisasterResponseAI",
            data=payload,
            headers={"Content-Type": "application/json",
                     "User-Agent": "DisasterResponseAI/2.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        # Country → approximate coordinates
        COUNTRY_COORDS = {
            "Afghanistan": (33.9, 67.7), "Bangladesh": (23.7, 90.4),
            "Brazil": (-14.2, -51.9), "China": (35.9, 104.2),
            "Colombia": (4.6, -74.1), "Ethiopia": (9.1, 40.5),
            "India": (20.6, 78.9), "Indonesia": (-0.8, 113.9),
            "Japan": (36.2, 138.3), "Kenya": (-0.0, 37.9),
            "Mexico": (23.6, -102.6), "Mozambique": (-18.7, 35.5),
            "Myanmar": (21.9, 95.9), "Nepal": (28.4, 84.1),
            "Nigeria": (9.1, 8.7), "Pakistan": (30.4, 69.3),
            "Peru": (-9.2, -75.0), "Philippines": (12.9, 121.8),
            "Somalia": (5.2, 46.2), "South Sudan": (6.9, 31.3),
            "Sudan": (12.9, 30.2), "Syria": (34.8, 38.9),
            "Turkey": (38.9, 35.2), "Uganda": (1.4, 32.3),
            "USA": (37.1, -95.7), "Vietnam": (14.1, 108.3),
            "Yemen": (15.6, 48.5), "Zimbabwe": (-19.0, 29.2),
        }

        TYPE_MAP = {
            "Flood": "flood", "Earthquake": "earthquake", "Cyclone": "cyclone",
            "Tsunami": "tsunami", "Wildfire": "wildfire", "Landslide": "landslide",
            "Drought": "drought", "Volcano": "volcano",
        }

        for item in data.get("data", []):
            f = item.get("fields", {})
            title = f.get("title", "")
            if not title:
                continue

            # Get country and coords
            countries = f.get("country", [])
            country_name = countries[0].get("name", "Unknown") if countries else "Unknown"
            coords = COUNTRY_COORDS.get(country_name, None)
            if not coords:
                # Try primary_country
                pc = f.get("primary_country", {})
                country_name = pc.get("name", country_name) if pc else country_name
                coords = COUNTRY_COORDS.get(country_name, (0.0, 0.0))

            # Get type
            types = f.get("type", [])
            dis_type = types[0].get("name", "unknown") if types else "unknown"
            event_type = TYPE_MAP.get(dis_type, dis_type.lower())

            # Severity based on status
            status = f.get("status", "ongoing")
            severity = "Red" if status == "alert" else "Orange" if status == "ongoing" else "Green"

            date_info = f.get("date", {})
            date_str = date_info.get("created", "")[:10] if date_info else ""

            url = f.get("url", "https://reliefweb.int")

            disasters.append(GlobalDisaster(
                event_id=f"rw_{item.get('id', len(disasters))}",
                event_type=event_type,
                title=title,
                country=country_name,
                severity=severity,
                severity_score={"Red": 3.0, "Orange": 2.0, "Green": 1.0}[severity],
                lat=coords[0], lon=coords[1],
                date=date_str,
                url=url,
                affected=0,
                description="",
            ))

    except Exception as e:
        print(f"  [ReliefWeb] Failed: {e.__class__.__name__}: {str(e)[:60]}")

    return disasters


def _current_fallback() -> list[GlobalDisaster]:
    """
    Static fallback with realistic current-era disasters.
    Used only when both GDACS and ReliefWeb are unreachable.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return [
        GlobalDisaster("eq_001", "earthquake", "M6.4 Earthquake — Eastern Turkey", "Turkey",
                       "Red", 3.0, 38.5, 43.4, today, "https://gdacs.org", 45000),
        GlobalDisaster("fl_001", "flood", "Severe Monsoon Flooding — Bangladesh", "Bangladesh",
                       "Red", 3.0, 23.8, 90.4, today, "https://gdacs.org", 280000),
        GlobalDisaster("tc_001", "cyclone", "Tropical Cyclone — Bay of Bengal", "India",
                       "Orange", 2.0, 15.2, 85.3, today, "https://gdacs.org", 95000),
        GlobalDisaster("fl_002", "flood", "Flash Floods — Pakistan Punjab", "Pakistan",
                       "Red", 3.0, 30.2, 71.5, today, "https://gdacs.org", 130000),
        GlobalDisaster("wf_001", "wildfire", "Wildfires — Southern Europe", "Greece",
                       "Orange", 2.0, 37.9, 23.7, today, "https://gdacs.org", 8000),
        GlobalDisaster("eq_002", "earthquake", "M5.8 Earthquake — Japan", "Japan",
                       "Orange", 2.0, 35.7, 139.7, today, "https://gdacs.org", 12000),
        GlobalDisaster("fl_003", "flood", "River Flooding — Nigeria", "Nigeria",
                       "Orange", 2.0, 9.1, 8.7, today, "https://gdacs.org", 75000),
        GlobalDisaster("ls_001", "landslide", "Landslides — Nepal", "Nepal",
                       "Orange", 2.0, 28.4, 84.1, today, "https://gdacs.org", 5000),
        GlobalDisaster("dr_001", "drought", "Severe Drought — Horn of Africa", "Somalia",
                       "Red", 3.0, 5.2, 46.2, today, "https://gdacs.org", 500000),
        GlobalDisaster("tc_002", "cyclone", "Tropical Storm — Philippines", "Philippines",
                       "Orange", 2.0, 12.9, 121.8, today, "https://gdacs.org", 60000),
    ]


def fetch_global_disasters() -> list[GlobalDisaster]:
    """
    Fetch real active disasters — tries multiple sources in order.
    1. GDACS RSS (primary — real-time)
    2. ReliefWeb API (fallback — always works from cloud)
    3. Static current-era data (last resort)
    """
    # Try GDACS first
    disasters = _fetch_gdacs()
    if disasters:
        print(f"  [GDACS] Fetched {len(disasters)} disasters from GDACS")
        return disasters[:50]

    # Try ReliefWeb
    disasters = _fetch_reliefweb()
    if disasters:
        print(f"  [ReliefWeb] Fetched {len(disasters)} disasters from ReliefWeb")
        return disasters[:50]

    # Last resort — static fallback
    print("  [GlobalDisasters] Both sources failed — using static fallback")
    return _current_fallback()
