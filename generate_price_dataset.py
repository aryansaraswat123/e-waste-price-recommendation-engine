"""Generate the e-waste pricing dataset from a material baseline CSV.

This is a scenario-data generator, not a live-market scraper. Generated rows are
explicitly marked synthetic so downstream code does not confuse them with
independently verified market observations.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List


REQUIRED_MATERIAL_COLUMNS = {
    "material_id",
    "category",
    "subcategory",
    "device_origin",
    "preferred_unit_for_collector",
    "typical_price_per_piece_inr_min",
    "typical_price_per_piece_inr_max",
    "estimated_value_inr_per_kg_min",
    "estimated_value_inr_per_kg_max",
}

CANONICAL_VISION_CATEGORIES = {
    "CRT",
    "LCD_LED",
    "PCB",
    "CABLES_WIRES",
    "BATTERIES",
    "MOTORS",
    "PLASTICS",
    "MOBILE_TABLETS",
}

LOCATIONS = [
    {"state": "Maharashtra", "city": "Pune", "cluster": "Kasba Peth Scrap Mandi / Hadapsar MIDC", "tier": "Tier 1", "price_factor": 1.00, "preferred_recycler": "Ecoreco Collection Center (Pune Hub)", "auth_no": "CPCB/EPR-EW/2023/MH-014", "trend_bias": "Rising"},
    {"state": "Maharashtra", "city": "Mumbai", "cluster": "Dharavi 13th Compound / Kurla CST Road", "tier": "Tier 1", "price_factor": 1.03, "preferred_recycler": "Eco Recycling Ltd (Ecoreco Mumbai HQ)", "auth_no": "CPCB/EPR-EW/2022/MH-003", "trend_bias": "Rising"},
    {"state": "Maharashtra", "city": "Nagpur", "cluster": "MIDC Hingna Industrial Area / Nandanvan", "tier": "Tier 2", "price_factor": 0.96, "preferred_recycler": "Suritex E-Waste Recyclers Nagpur", "auth_no": "MPCB/ROT-NAG/EW-2023/08", "trend_bias": "Stable"},
    {"state": "Delhi NCR", "city": "Delhi", "cluster": "Mayapuri Industrial Area Phase-II / Mandoli", "tier": "Tier 1", "price_factor": 1.04, "preferred_recycler": "Attero Recycling NCR Central Depot", "auth_no": "CPCB/EPR-EW/2022/DL-001", "trend_bias": "Rising"},
    {"state": "Karnataka", "city": "Bengaluru", "cluster": "Peenya Industrial Area / SP Road Electronic Market", "tier": "Tier 1", "price_factor": 1.05, "preferred_recycler": "E-Parisaraa Pvt Ltd (Dabaspet Hub)", "auth_no": "CPCB/EPR-EW/2022/KA-002", "trend_bias": "Rising"},
    {"state": "Tamil Nadu", "city": "Chennai", "cluster": "Ambattur Industrial Estate / Guindy", "tier": "Tier 1", "price_factor": 1.01, "preferred_recycler": "Trishyiraya Recycling India Pvt Ltd", "auth_no": "CPCB/EPR-EW/2023/TN-009", "trend_bias": "Stable"},
    {"state": "Telangana", "city": "Hyderabad", "cluster": "Kattedan Industrial Area / Sanathnagar", "tier": "Tier 1", "price_factor": 0.99, "preferred_recycler": "Earth Sense Recycle Pvt Ltd Hyderabad", "auth_no": "CPCB/EPR-EW/2022/TS-005", "trend_bias": "Stable"},
    {"state": "Gujarat", "city": "Ahmedabad", "cluster": "Odhav / Vatva GIDC Industrial Estate", "tier": "Tier 1", "price_factor": 1.02, "preferred_recycler": "ECS Environment Ltd Ahmedabad", "auth_no": "CPCB/EPR-EW/2022/GJ-007", "trend_bias": "Rising"},
    {"state": "West Bengal", "city": "Kolkata", "cluster": "Howrah Metal Foundry Cluster / Topsia", "tier": "Tier 1", "price_factor": 0.97, "preferred_recycler": "Greentech Recycling Kolkata Hub", "auth_no": "CPCB/EPR-EW/2023/WB-004", "trend_bias": "Stable"},
    {"state": "Uttar Pradesh", "city": "Lucknow", "cluster": "Transport Nagar / Talkatora Industrial Area", "tier": "Tier 2", "price_factor": 0.95, "preferred_recycler": "Karo Sambhav UP Aggregation Partner", "auth_no": "CPCB/EPR-EW/2023/UP-011", "trend_bias": "Softening"},
    {"state": "Madhya Pradesh", "city": "Indore", "cluster": "Sanwer Road Industrial Area / Palda", "tier": "Tier 2", "price_factor": 0.96, "preferred_recycler": "The Kabadiwala Authorized MRF Hub", "auth_no": "CPCB/EPR-EW/2023/MP-006", "trend_bias": "Stable"},
    {"state": "Rajasthan", "city": "Jaipur", "cluster": "Vishwakarma Industrial Area (VKIA) / Sitapura", "tier": "Tier 2", "price_factor": 0.95, "preferred_recycler": "Greenscape Eco Management Jaipur", "auth_no": "CPCB/EPR-EW/2022/RJ-003", "trend_bias": "Stable"},
]

DATES = [
    {"date": "2026-07-15", "factor": 0.965, "label": "Historical"},
    {"date": "2026-08-01", "factor": 0.978, "label": "Historical"},
    {"date": "2026-08-15", "factor": 0.985, "label": "Historical"},
    {"date": "2026-09-01", "factor": 0.995, "label": "Recent"},
    {"date": "2026-09-05", "factor": 1.000, "label": "Current"},
]

MARKET_DRIVERS = {
    "Cable": {"Rising": "Configured cable-market scenario: rising.", "Stable": "Configured cable-market scenario: stable.", "Softening": "Configured cable-market scenario: softening."},
    "PCB": {"Rising": "Configured PCB-market scenario: rising.", "Stable": "Configured PCB-market scenario: stable.", "Softening": "Configured PCB-market scenario: softening."},
    "Battery": {"Rising": "Configured battery-market scenario: rising.", "Stable": "Configured battery-market scenario: stable.", "Softening": "Configured battery-market scenario: softening."},
    "Motor": {"Rising": "Configured motor-market scenario: rising.", "Stable": "Configured motor-market scenario: stable.", "Softening": "Configured motor-market scenario: softening."},
    "Mixed Plastic": {"Rising": "Configured plastic-market scenario: rising.", "Stable": "Configured plastic-market scenario: stable.", "Softening": "Configured plastic-market scenario: softening."},
    "CRT": {"Rising": "Configured CRT-market scenario: rising.", "Stable": "Configured CRT-market scenario: stable.", "Softening": "Configured CRT-market scenario: softening."},
    "LCD Panel": {"Rising": "Configured LCD/LED-market scenario: rising.", "Stable": "Configured LCD/LED-market scenario: stable.", "Softening": "Configured LCD/LED-market scenario: softening."},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def canonical_vision_category(category: str, subcategory: str = "", device_origin: str = "") -> str:
    """Map material-dataset labels to the exact 8 image-model categories."""
    c = clean_text(category).lower()
    s = clean_text(subcategory).lower()
    o = clean_text(device_origin).lower()

    # Category takes priority so a mobile-origin PCB remains PCB rather than MOBILE_TABLETS.
    if "pcb" in c or "printed circuit" in c or "circuit board" in c:
        return "PCB"
    if "cable" in c or "wire" in c:
        return "CABLES_WIRES"
    if "battery" in c or "cell" in c:
        return "BATTERIES"
    if "motor" in c:
        return "MOTORS"
    if "plastic" in c or "polymer" in c:
        return "PLASTICS"
    if c == "crt" or "cathode ray" in c:
        return "CRT"
    if "lcd" in c or "led" in c or "display" in c or "panel" in c:
        return "LCD_LED"
    if "mobile" in c or "phone" in c or "tablet" in c or "smartphone" in c:
        return "MOBILE_TABLETS"

    # Only use secondary text for whole-device records whose category itself is generic.
    combined = f"{s} {o}"
    if any(k in combined for k in ("mobile phone", "smartphone", "tablet")) and not any(
        k in combined for k in ("pcb", "board", "cable", "wire", "battery")
    ):
        return "MOBILE_TABLETS"

    raise ValueError(
        f"Cannot map material to one of the 8 vision categories: "
        f"category={category!r}, subcategory={subcategory!r}, device_origin={device_origin!r}"
    )


def to_float(row: Dict[str, str], column: str) -> float:
    value = clean_text(row.get(column, ""))
    if value == "":
        return 0.0
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value in {column}: {value!r}") from exc


def smart_round(val: float):
    if val >= 1000:
        return round(val / 50) * 50
    if val >= 100:
        return round(val / 5) * 5
    if val >= 20:
        return round(val)
    rounded = round(val, 1)
    return int(rounded) if rounded.is_integer() else rounded


def load_materials(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Material dataset not found: {path}. Put your real material_dataset.csv there "
            "or pass --materials /path/to/material_dataset.csv"
        )

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Material dataset has no header row.")
        missing = REQUIRED_MATERIAL_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Material dataset is missing required columns: {sorted(missing)}")
        rows = list(reader)

    if not rows:
        raise ValueError("Material dataset contains no material records.")
    return rows


def category_location_bonus(category: str, city: str) -> float:
    if category == "PCB" and city in {"Bengaluru", "Delhi", "Mumbai"}:
        return 1.05
    if category == "Mixed Plastic" and city in {"Ahmedabad", "Surat"}:
        return 1.06
    if category == "Battery" and city in {"Pune", "Chennai", "Delhi"}:
        return 1.04
    return 1.0


def is_benchmark_subcategory(subcategory: str) -> bool:
    keys = (
        "Mobile", "Motherboard", "RAM", "Bare Bright", "Insulated", "Inverter",
        "Car", "Fan", "32 inch", "21 inch Curved", "White / Milky ABS", "Black ABS",
    )
    return any(key.lower() in clean_text(subcategory).lower() for key in keys)


def generate_rows(materials: Iterable[Dict[str, str]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    record_counter = 1

    for loc in LOCATIONS:
        state_code = loc["state"][:2].upper() if loc["state"] != "Delhi NCR" else "DL"
        city_code = loc["city"][:3].upper()

        for mat in materials:
            mat_id = clean_text(mat["material_id"])
            cat = clean_text(mat["category"])
            subcat = clean_text(mat["subcategory"])
            origin = clean_text(mat["device_origin"])
            preferred_unit = clean_text(mat["preferred_unit_for_collector"]).lower()
            vision_category = canonical_vision_category(cat, subcat, origin)

            piece_max = to_float(mat, "typical_price_per_piece_inr_max")
            if preferred_unit == "per_piece" and piece_max > 0:
                unit = "per_piece"
                base_min = to_float(mat, "typical_price_per_piece_inr_min")
                base_max = piece_max
            else:
                unit = "per_kg"
                base_min = to_float(mat, "estimated_value_inr_per_kg_min")
                base_max = to_float(mat, "estimated_value_inr_per_kg_max")

            if base_min < 0 or base_max < 0 or base_max < base_min:
                raise ValueError(
                    f"Invalid base price range for material {mat_id}: min={base_min}, max={base_max}"
                )
            if base_max == 0:
                raise ValueError(f"Material {mat_id} has no usable positive price baseline.")

            base_mid = (base_min + base_max) / 2.0
            cat_loc_factor = category_location_bonus(cat, loc["city"])
            loc_adjusted_mid = base_mid * float(loc["price_factor"]) * cat_loc_factor

            for d in DATES:
                if d["label"] != "Current" and not is_benchmark_subcategory(subcat):
                    continue

                date_adjusted = loc_adjusted_mid * float(d["factor"])
                mandi_price = smart_round(date_adjusted)
                informal_price = smart_round(date_adjusted * 0.86)
                authorized_price = smart_round(date_adjusted * 1.08)
                range_min = smart_round(float(informal_price) * 0.95)
                range_max = smart_round(float(authorized_price) * 1.05)
                formal_bonus = smart_round(float(authorized_price) - float(informal_price))
                formal_bonus_pct = (
                    round(((float(authorized_price) - float(informal_price)) / float(informal_price)) * 100, 1)
                    if float(informal_price) > 0 else 0.0
                )

                trend = loc["trend_bias"]
                trend_detail = MARKET_DRIVERS.get(cat, {}).get(
                    trend, "Configured synthetic market scenario."
                )

                record_id = f"PRC-{state_code}-{city_code}-{record_counter:05d}"
                record_counter += 1
                time_str = "10:30:00" if d["label"] == "Current" else "11:00:00"

                rows.append({
                    "price_record_id": record_id,
                    "material_id": mat_id,
                    "vision_category": vision_category,
                    "category": cat,
                    "subcategory": subcat,
                    "device_origin": origin,
                    "material_source_name": clean_text(mat.get("source_name", "")),
                    "material_source_type": clean_text(mat.get("source_type", "")),
                    "material_source_url": clean_text(mat.get("source_url", "")),
                    "material_source_observation_date": clean_text(mat.get("source_observation_date", "")),
                    "material_evidence_level": clean_text(mat.get("evidence_level", "")),
                    "material_notes": clean_text(mat.get("notes", "")),
                    "location_state": loc["state"],
                    "location_city": loc["city"],
                    "location_market_cluster": loc["cluster"],
                    "city_tier": loc["tier"],
                    "date_recorded": d["date"],
                    "time_recorded": time_str,
                    "unit_of_measure": unit,
                    "source_base_price_min_inr": base_min,
                    "source_base_price_max_inr": base_max,
                    "source_base_price_mid_inr": round(base_mid, 2),
                    "location_price_factor": loc["price_factor"],
                    "category_location_factor": cat_loc_factor,
                    "date_factor": d["factor"],
                    "doorstep_informal_price_inr": informal_price,
                    "wholesale_mandi_price_inr": mandi_price,
                    "authorized_recycler_offered_price_inr": authorized_price,
                    "market_range_min_inr": range_min,
                    "market_range_max_inr": range_max,
                    "formal_channel_bonus_inr": formal_bonus,
                    "formal_bonus_percentage": formal_bonus_pct,
                    "price_trend_30d": trend,
                    "price_trend_detail": trend_detail,
                    "top_authorized_buyer": loc["preferred_recycler"],
                    "buyer_authorization_no": loc["auth_no"],
                    "data_source": "Synthetic scenario generated from material baselines and configured location/date factors",
                    "verification_status": "Synthetic - requires independent market verification",
                    "is_synthetic": True,
                    "generation_method": "base_mid * location_factor * category_location_factor * date_factor",
                })

    return rows


def write_csv(rows: List[Dict[str, object]], output_path: Path) -> None:
    if not rows:
        raise ValueError("No pricing rows were generated.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate e-waste price scenario dataset")
    parser.add_argument("--materials", default="data/material_dataset.csv", help="Input material CSV")
    parser.add_argument("--output", default="data/price_dataset.csv", help="Output pricing CSV")
    args = parser.parse_args()

    materials_path = Path(args.materials)
    output_path = Path(args.output)
    materials = load_materials(materials_path)
    rows = generate_rows(materials)
    write_csv(rows, output_path)

    mapped = sorted({row["vision_category"] for row in rows})
    print(f"Loaded {len(materials)} materials.")
    print(f"Generated {len(rows)} price records.")
    print(f"Vision categories present: {mapped}")
    print(f"Successfully written to {output_path.resolve()}")


if __name__ == "__main__":
    main()
