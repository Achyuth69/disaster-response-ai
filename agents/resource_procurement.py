"""
agents/resource_procurement.py — Resource Procurement AI.

When resources run out, AI generates procurement orders:
- Identifies nearest suppliers
- Estimates delivery time
- Calculates cost
- Generates purchase orders

Connects supply chain to disaster response in real-time.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Supplier:
    supplier_id: str
    name: str
    type: str           # "pharmacy" | "warehouse" | "hospital" | "ngo" | "government"
    resource_types: list[str]
    lat: float
    lon: float
    address: str
    contact: str
    stock_available: dict  # resource → quantity
    delivery_time_min: float
    cost_per_unit: dict    # resource → cost in INR


@dataclass
class ProcurementOrder:
    order_id: str
    resource: str
    quantity_needed: int
    supplier: Supplier
    estimated_delivery_min: float
    total_cost_inr: float
    priority: str
    status: str = "pending"


# Hyderabad supplier database
HYDERABAD_SUPPLIERS = [
    Supplier(
        supplier_id="SUP001",
        name="Apollo Pharmacy — Kukatpally",
        type="pharmacy",
        resource_types=["medical_kits", "medicines", "oxygen"],
        lat=17.494, lon=78.408,
        address="KPHB Colony, Kukatpally, Hyderabad",
        contact="040-23456789",
        stock_available={"medical_kits": 500, "medicines": 2000, "oxygen_cylinders": 50},
        delivery_time_min=45.0,
        cost_per_unit={"medical_kits": 850, "medicines": 200, "oxygen_cylinders": 1500},
    ),
    Supplier(
        supplier_id="SUP002",
        name="SDRF Emergency Depot — Begumpet",
        type="government",
        resource_types=["rescue_teams", "boats", "medical_kits", "food_supply"],
        lat=17.453, lon=78.467,
        address="Begumpet, Hyderabad",
        contact="040-27852222",
        stock_available={"rescue_teams": 20, "boats": 8, "medical_kits": 1000, "food_supply": 5000},
        delivery_time_min=30.0,
        cost_per_unit={"rescue_teams": 0, "boats": 0, "medical_kits": 0, "food_supply": 0},
    ),
    Supplier(
        supplier_id="SUP003",
        name="Red Cross India — Secunderabad",
        type="ngo",
        resource_types=["medical_kits", "food_supply", "shelter_kits"],
        lat=17.440, lon=78.498,
        address="Minister Road, Secunderabad",
        contact="040-27893456",
        stock_available={"medical_kits": 300, "food_supply": 2000, "shelter_kits": 500},
        delivery_time_min=25.0,
        cost_per_unit={"medical_kits": 0, "food_supply": 0, "shelter_kits": 0},
    ),
    Supplier(
        supplier_id="SUP004",
        name="FMCG Warehouse — LB Nagar",
        type="warehouse",
        resource_types=["food_supply", "water_bottles", "blankets"],
        lat=17.346, lon=78.554,
        address="LB Nagar Industrial Area, Hyderabad",
        contact="040-24567890",
        stock_available={"food_supply": 10000, "water_bottles": 50000, "blankets": 2000},
        delivery_time_min=60.0,
        cost_per_unit={"food_supply": 150, "water_bottles": 20, "blankets": 250},
    ),
    Supplier(
        supplier_id="SUP005",
        name="GHMC Emergency Store — Uppal",
        type="government",
        resource_types=["boats", "rescue_equipment", "generators"],
        lat=17.399, lon=78.559,
        address="Uppal, Hyderabad",
        contact="040-21234567",
        stock_available={"boats": 5, "rescue_equipment": 100, "generators": 10},
        delivery_time_min=20.0,
        cost_per_unit={"boats": 0, "rescue_equipment": 0, "generators": 0},
    ),
    Supplier(
        supplier_id="SUP006",
        name="Army Supply Depot — Secunderabad Cantonment",
        type="government",
        resource_types=["rescue_teams", "boats", "medical_kits", "food_supply", "helicopters"],
        lat=17.440, lon=78.500,
        address="Secunderabad Cantonment, Hyderabad",
        contact="040-27891234 (Army EOC)",
        stock_available={"rescue_teams": 100, "boats": 20, "medical_kits": 5000,
                         "food_supply": 20000, "helicopters": 4},
        delivery_time_min=60.0,
        cost_per_unit={"rescue_teams": 0, "boats": 0, "medical_kits": 0,
                       "food_supply": 0, "helicopters": 0},
    ),
]


def generate_procurement_orders(
    depleted_resources: list[str],
    quantities_needed: dict,
    base_lat: float,
    base_lon: float,
) -> list[ProcurementOrder]:
    """Generate procurement orders for depleted resources."""
    import math

    def dist(lat1, lon1, lat2, lon2):
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
            math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return 6371 * 2 * math.asin(math.sqrt(max(0, a)))

    orders = []
    order_num = 1

    for resource in depleted_resources:
        needed = quantities_needed.get(resource, 50)

        # Find best supplier (closest with stock)
        candidates = []
        for sup in HYDERABAD_SUPPLIERS:
            if resource in sup.resource_types and sup.stock_available.get(resource, 0) > 0:
                d = dist(base_lat, base_lon, sup.lat, sup.lon)
                travel_time = (d / 30) * 60  # 30 km/h in disaster conditions
                total_time = sup.delivery_time_min + travel_time
                candidates.append((total_time, sup))

        if not candidates:
            continue

        candidates.sort(key=lambda x: x[0])
        best_time, best_sup = candidates[0]

        qty = min(needed, best_sup.stock_available.get(resource, needed))
        cost = qty * best_sup.cost_per_unit.get(resource, 0)

        priority = "CRITICAL" if resource in ("rescue_teams", "medical_kits") else "HIGH"

        orders.append(ProcurementOrder(
            order_id=f"PO-{order_num:04d}",
            resource=resource,
            quantity_needed=qty,
            supplier=best_sup,
            estimated_delivery_min=round(best_time, 1),
            total_cost_inr=cost,
            priority=priority,
        ))
        order_num += 1

    return orders
