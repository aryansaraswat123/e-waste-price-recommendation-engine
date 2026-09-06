"""Location-aware e-waste price calculation and recommendation engine.

The engine is intentionally transparent and deterministic.  It does not pretend
that the synthetic city/date expansion in ``price_dataset.csv`` is a learned
market forecast.  It combines the latest matched scenario rows with robust
statistics and exposes uncertainty, provenance, and fallback quality.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


CHANNEL_COLUMNS = {
    "informal": "doorstep_informal_price_inr",
    "mandi": "wholesale_mandi_price_inr",
    "authorized": "authorized_recycler_offered_price_inr",
}

CATEGORY_ALIASES = {
    "CRT": "CRT",
    "LCD": "LCD_LED",
    "LED": "LCD_LED",
    "LCD_LED": "LCD_LED",
    "LCD/LED": "LCD_LED",
    "LCD/LED DISPLAYS": "LCD_LED",
    "PCB": "PCB",
    "CABLE": "CABLES_WIRES",
    "CABLES": "CABLES_WIRES",
    "WIRE": "CABLES_WIRES",
    "WIRES": "CABLES_WIRES",
    "CABLES_WIRES": "CABLES_WIRES",
    "CABLES & WIRES": "CABLES_WIRES",
    "BATTERY": "BATTERIES",
    "BATTERIES": "BATTERIES",
    "MOTOR": "MOTORS",
    "MOTORS": "MOTORS",
    "PLASTIC": "PLASTICS",
    "PLASTICS": "PLASTICS",
    "MIXED PLASTIC": "PLASTICS",
    "MOBILE": "MOBILE_TABLETS",
    "MOBILES": "MOBILE_TABLETS",
    "MOBILE_TABLETS": "MOBILE_TABLETS",
    "MOBILE PHONES / TABLETS": "MOBILE_TABLETS",
    "MOBILE PHONES/TABLETS": "MOBILE_TABLETS",
}

STATE_ALIASES = {
    "up": "uttar pradesh",
    "u.p.": "uttar pradesh",
    "uttar pradesh": "uttar pradesh",
    "delhi": "delhi ncr",
    "nct delhi": "delhi ncr",
    "nct of delhi": "delhi ncr",
    "delhi ncr": "delhi ncr",
    "maharastra": "maharashtra",
}

CITY_ALIASES = {
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "calcutta": "kolkata",
}

REQUIRED_PRICE_COLUMNS = {
    "vision_category",
    "subcategory",
    "location_state",
    "location_city",
    "date_recorded",
    "unit_of_measure",
    "doorstep_informal_price_inr",
    "wholesale_mandi_price_inr",
    "authorized_recycler_offered_price_inr",
    "market_range_min_inr",
    "market_range_max_inr",
}


@dataclass(frozen=True)
class QuoteRequest:
    category: str
    state: str
    city: str
    quantity: float
    total_weight_kg: float
    channel: str = "authorized"
    unit: str = "auto"
    subcategory: Optional[str] = None
    as_of_date: Optional[str] = None


class PriceEngine:
    """Calculate an explainable scrap-value estimate from a pricing dataset.

    Matching order
    --------------
    1. category (+ optional exact subcategory)
    2. exact city + state
    3. state fallback
    4. national fallback
    5. newest available pricing date
    6. requested/automatically selected pricing unit

    The recommended rate is the median of the selected channel.  For a broad
    image category, the engine widens the displayed rate/value range to include
    variation across different materials within that category.
    """

    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Price dataset not found: {self.dataset_path}")
        self.df = pd.read_csv(self.dataset_path)
        self._validate_and_prepare()

    @staticmethod
    def _norm_text(value: object) -> str:
        return " ".join(str(value or "").strip().split()).casefold()

    @classmethod
    def _norm_state(cls, value: object) -> str:
        n = cls._norm_text(value)
        return STATE_ALIASES.get(n, n)

    @classmethod
    def _norm_city(cls, value: object) -> str:
        n = cls._norm_text(value)
        return CITY_ALIASES.get(n, n)

    @classmethod
    def canonical_category(cls, category: str) -> str:
        key = " ".join(str(category).strip().upper().split())
        if key in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[key]
        raise ValueError(
            f"Unsupported category {category!r}. Expected one of: "
            "CRT, LCD_LED, PCB, CABLES_WIRES, BATTERIES, MOTORS, PLASTICS, MOBILE_TABLETS"
        )

    def _validate_and_prepare(self) -> None:
        missing = REQUIRED_PRICE_COLUMNS - set(self.df.columns)
        if missing:
            raise ValueError(f"Pricing dataset is missing required columns: {sorted(missing)}")
        if self.df.empty:
            raise ValueError("Pricing dataset is empty.")

        self.df["date_recorded"] = pd.to_datetime(self.df["date_recorded"], errors="coerce")
        if self.df["date_recorded"].isna().any():
            bad = int(self.df["date_recorded"].isna().sum())
            raise ValueError(f"Pricing dataset has {bad} invalid date_recorded values.")

        numeric_cols = [
            "doorstep_informal_price_inr",
            "wholesale_mandi_price_inr",
            "authorized_recycler_offered_price_inr",
            "market_range_min_inr",
            "market_range_max_inr",
        ]
        for col in numeric_cols:
            self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
            if self.df[col].isna().any():
                raise ValueError(f"Pricing dataset has non-numeric or missing values in {col}.")
            if (self.df[col] < 0).any():
                raise ValueError(f"Pricing dataset contains negative values in {col}.")

        self.df["vision_category"] = self.df["vision_category"].astype(str).str.strip().str.upper()
        valid = set(CATEGORY_ALIASES.values())
        invalid_categories = sorted(set(self.df["vision_category"]) - valid)
        if invalid_categories:
            raise ValueError(f"Unknown vision_category values in dataset: {invalid_categories}")

        self.df["unit_of_measure"] = self.df["unit_of_measure"].astype(str).str.strip().str.lower()
        invalid_units = sorted(set(self.df["unit_of_measure"]) - {"per_kg", "per_piece"})
        if invalid_units:
            raise ValueError(f"Unsupported unit_of_measure values: {invalid_units}")

        if (self.df["market_range_max_inr"] < self.df["market_range_min_inr"]).any():
            raise ValueError("Pricing dataset contains market_range_max_inr < market_range_min_inr.")

    def available_subcategories(self, category: str) -> list[str]:
        canonical = self.canonical_category(category)
        rows = self.df[self.df["vision_category"] == canonical]
        return sorted(rows["subcategory"].dropna().astype(str).unique().tolist())

    def _resolve_subcategory(self, data: pd.DataFrame, requested: Optional[str]) -> tuple[pd.DataFrame, bool, Optional[str]]:
        if not requested:
            return data, False, None

        target = self._norm_text(requested)
        normalized = data["subcategory"].map(self._norm_text)
        exact = data[normalized == target]
        if not exact.empty:
            matched_name = str(exact["subcategory"].iloc[0])
            return exact, True, matched_name

        choices = sorted(data["subcategory"].dropna().astype(str).unique().tolist())
        suggestions = get_close_matches(str(requested), choices, n=5, cutoff=0.45)
        suffix = f" Close matches: {suggestions}" if suggestions else ""
        raise LookupError(f"Subcategory {requested!r} was not found for this category.{suffix}")

    def _location_match(self, data: pd.DataFrame, state: str, city: str) -> tuple[pd.DataFrame, str]:
        state_n = self._norm_state(state)
        city_n = self._norm_city(city)

        state_series = data["location_state"].map(self._norm_state)
        city_series = data["location_city"].map(self._norm_city)

        city_rows = data[(state_series == state_n) & (city_series == city_n)]
        if not city_rows.empty:
            return city_rows, "city"

        state_rows = data[state_series == state_n]
        if not state_rows.empty:
            return state_rows, "state"

        return data, "national"

    @staticmethod
    def _spread_level(relative_iqr: float) -> str:
        if relative_iqr <= 0.25:
            return "low"
        if relative_iqr <= 0.75:
            return "medium"
        return "high"

    @staticmethod
    def _freshness_band(days_old: int) -> str:
        if days_old <= 7:
            return "fresh"
        if days_old <= 30:
            return "recent"
        if days_old <= 90:
            return "aging"
        return "stale"

    @staticmethod
    def _direct_evidence_ratio(data: pd.DataFrame) -> float:
        if "material_evidence_level" not in data.columns:
            return 0.0
        values = data["material_evidence_level"].fillna("").astype(str).str.upper()
        if len(values) == 0:
            return 0.0
        return float(values.str.startswith("DIRECT").mean())

    @staticmethod
    def _uses_synthetic(data: pd.DataFrame) -> bool:
        if "is_synthetic" not in data.columns:
            return False
        values = data["is_synthetic"].astype(str).str.casefold()
        return bool(values.isin({"true", "1", "yes"}).any())

    @staticmethod
    def _quality_score(
        match_level: str,
        subcategory_used: bool,
        freshness_days: int,
        direct_evidence_ratio: float,
        spread_level: str,
        uses_synthetic_data: bool,
    ) -> int:
        score = {"city": 30, "state": 20, "national": 10}[match_level]
        score += 30 if subcategory_used else 12

        if freshness_days <= 7:
            score += 20
        elif freshness_days <= 30:
            score += 15
        elif freshness_days <= 90:
            score += 8
        else:
            score += 3

        if direct_evidence_ratio >= 0.90:
            score += 15
        elif direct_evidence_ratio >= 0.50:
            score += 10
        else:
            score += 5

        score += {"low": 5, "medium": 2, "high": 0}[spread_level]

        # Synthetic location/date expansion is useful for a prototype but is not
        # equivalent to an independently observed live market quote.
        if uses_synthetic_data:
            score -= 20

        return max(0, min(100, int(round(score))))

    @staticmethod
    def _quality_label(score: int) -> str:
        if score >= 75:
            return "strong-prototype-estimate"
        if score >= 60:
            return "moderate-prototype-estimate"
        if score >= 45:
            return "broad-or-fallback-estimate"
        return "low-specificity-estimate"

    @staticmethod
    def _parse_as_of(value: Optional[str]) -> pd.Timestamp:
        if value is None:
            return pd.Timestamp(date.today())
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            raise ValueError("as_of_date must be a valid date such as 2026-09-05")
        return pd.Timestamp(parsed).normalize()

    def quote(self, request: QuoteRequest) -> Dict[str, object]:
        category = self.canonical_category(request.category)
        channel = str(request.channel).strip().lower()
        if channel not in CHANNEL_COLUMNS:
            raise ValueError(f"channel must be one of {sorted(CHANNEL_COLUMNS)}")
        if request.quantity < 0:
            raise ValueError("quantity cannot be negative")
        if request.total_weight_kg < 0:
            raise ValueError("total_weight_kg cannot be negative")
        if not str(request.state).strip() or not str(request.city).strip():
            raise ValueError("state and city are required")

        data = self.df[self.df["vision_category"] == category].copy()
        if data.empty:
            raise LookupError(f"No pricing records for category {category}")

        data, subcategory_used, matched_subcategory = self._resolve_subcategory(data, request.subcategory)
        data, match_level = self._location_match(data, request.state, request.city)

        latest_date = data["date_recorded"].max()
        data = data[data["date_recorded"] == latest_date].copy()

        available_units = sorted(data["unit_of_measure"].dropna().unique().tolist())
        requested_unit = str(request.unit).strip().lower()
        if requested_unit != "auto":
            if requested_unit not in {"per_kg", "per_piece"}:
                raise ValueError("unit must be auto, per_kg, or per_piece")
            if requested_unit not in available_units:
                raise LookupError(
                    f"No {requested_unit} records available for this matched quote. "
                    f"Available units: {available_units}"
                )
            selected_unit = requested_unit
            unit_resolution = "explicit"
        elif len(available_units) == 1:
            selected_unit = available_units[0]
            unit_resolution = "only_available_unit"
        elif "per_kg" in available_units and request.total_weight_kg > 0:
            selected_unit = "per_kg"
            unit_resolution = "auto_preferred_per_kg_because_total_weight_was_supplied"
        elif "per_piece" in available_units and request.quantity > 0:
            selected_unit = "per_piece"
            unit_resolution = "auto_per_piece"
        else:
            raise ValueError(
                f"Cannot choose pricing unit automatically. Available units: {available_units}; "
                "provide unit='per_kg' or unit='per_piece'."
            )

        data = data[data["unit_of_measure"] == selected_unit].copy()
        if data.empty:
            raise LookupError("No rows remain after unit selection.")

        channel_col = CHANNEL_COLUMNS[channel]
        rates = data[channel_col].astype(float)
        informal_rate = float(data["doorstep_informal_price_inr"].median())
        mandi_rate = float(data["wholesale_mandi_price_inr"].median())
        authorized_rate = float(data["authorized_recycler_offered_price_inr"].median())
        recommended_rate = float(rates.median())

        q10 = float(rates.quantile(0.10))
        q25 = float(rates.quantile(0.25))
        q75 = float(rates.quantile(0.75))
        q90 = float(rates.quantile(0.90))
        iqr = q75 - q25
        relative_iqr = float(iqr / recommended_rate) if recommended_rate > 0 else 0.0
        spread_level = self._spread_level(relative_iqr)

        # For a specific subcategory, the row-level market range is the most
        # meaningful range.  For a broad image category, include material-grade
        # variation by taking robust tails across all matched subcategories.
        if subcategory_used:
            min_rate = float(data["market_range_min_inr"].median())
            max_rate = float(data["market_range_max_inr"].median())
            range_method = "matched_subcategory_market_range"
        else:
            min_rate = float(data["market_range_min_inr"].quantile(0.10))
            max_rate = float(data["market_range_max_inr"].quantile(0.90))
            range_method = "broad_category_10th_to_90th_percentile_with_market_range"

        if selected_unit == "per_kg":
            if request.total_weight_kg <= 0:
                raise ValueError("total_weight_kg must be > 0 for per_kg pricing")
            multiplier = float(request.total_weight_kg)
            multiplier_label = "total_weight_kg"
        else:
            if request.quantity <= 0:
                raise ValueError("quantity must be > 0 for per_piece pricing")
            multiplier = float(request.quantity)
            multiplier_label = "quantity"

        as_of = self._parse_as_of(request.as_of_date)
        freshness_days = max(0, int((as_of - latest_date.normalize()).days))
        future_dated = bool(latest_date.normalize() > as_of)
        direct_ratio = self._direct_evidence_ratio(data)
        uses_synthetic_data = self._uses_synthetic(data)
        quality_score = self._quality_score(
            match_level,
            subcategory_used,
            freshness_days,
            direct_ratio,
            spread_level,
            uses_synthetic_data,
        )

        warnings: list[str] = []
        if not subcategory_used:
            warnings.append(
                "Broad image category used. Different material grades/subcategories can have materially different prices."
            )
        if spread_level == "high":
            warnings.append("Matched rates have high internal variation; treat the displayed value as a broad estimate.")
        if match_level == "state":
            warnings.append("Exact city was unavailable; state-level fallback pricing was used.")
        elif match_level == "national":
            warnings.append("Exact city/state were unavailable; national fallback pricing was used.")
        if freshness_days > 30:
            warnings.append(f"Pricing snapshot is {freshness_days} days old relative to the requested as-of date.")
        if future_dated:
            warnings.append("Pricing snapshot is dated after the requested as-of date.")
        if uses_synthetic_data:
            warnings.append(
                "Location/date prices are synthetic scenario estimates derived from material baselines; independent live-market verification is required for production use."
            )

        matched_cities = sorted(data["location_city"].dropna().astype(str).unique().tolist())
        matched_states = sorted(data["location_state"].dropna().astype(str).unique().tolist())

        quote: Dict[str, object] = {
            "category": category,
            "requested_subcategory": request.subcategory,
            "subcategory_matched": subcategory_used,
            "matched_subcategory": matched_subcategory,
            "requested_state": request.state,
            "requested_city": request.city,
            "match_level": match_level,
            "matched_states": matched_states,
            "matched_cities": matched_cities,
            "pricing_date": latest_date.strftime("%Y-%m-%d"),
            "as_of_date": as_of.strftime("%Y-%m-%d"),
            "freshness_days": freshness_days,
            "freshness_band": self._freshness_band(freshness_days),
            "unit": selected_unit,
            "unit_resolution": unit_resolution,
            "quantity": float(request.quantity),
            "total_weight_kg": float(request.total_weight_kg),
            "pricing_channel": channel,
            "informal_rate_inr": round(informal_rate, 2),
            "mandi_rate_inr": round(mandi_rate, 2),
            "authorized_rate_inr": round(authorized_rate, 2),
            "recommended_rate_inr": round(recommended_rate, 2),
            "rate_q10_inr": round(q10, 2),
            "rate_q25_inr": round(q25, 2),
            "rate_q75_inr": round(q75, 2),
            "rate_q90_inr": round(q90, 2),
            "rate_iqr_inr": round(iqr, 2),
            "relative_iqr": round(relative_iqr, 3),
            "spread_level": spread_level,
            "market_rate_min_inr": round(min_rate, 2),
            "market_rate_max_inr": round(max_rate, 2),
            "range_method": range_method,
            "calculation_basis": f"{multiplier_label} × recommended_rate_inr",
            "estimated_value_inr": round(multiplier * recommended_rate, 2),
            "estimated_value_min_inr": round(multiplier * min_rate, 2),
            "estimated_value_max_inr": round(multiplier * max_rate, 2),
            "data_points_used": int(len(data)),
            "direct_material_evidence_ratio": round(direct_ratio, 3),
            "uses_synthetic_data": uses_synthetic_data,
            "quote_quality_score": quality_score,
            "estimate_quality": self._quality_label(quality_score),
            "warnings": warnings,
        }

        if "material_evidence_level" in data.columns:
            quote["material_evidence_levels"] = sorted(
                data["material_evidence_level"].fillna("").astype(str).unique().tolist()
            )
        if "material_source_name" in data.columns:
            quote["material_source_names"] = sorted(
                {x for x in data["material_source_name"].fillna("").astype(str).tolist() if x}
            )
        if "verification_status" in data.columns:
            quote["verification_statuses"] = sorted(data["verification_status"].astype(str).unique().tolist())
        if "data_source" in data.columns:
            quote["data_sources"] = sorted(data["data_source"].astype(str).unique().tolist())
        if "top_authorized_buyer" in data.columns:
            quote["suggested_authorized_buyers"] = sorted(
                {x for x in data["top_authorized_buyer"].fillna("").astype(str).tolist() if x}
            )

        return quote


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate an e-waste scrap price quote")
    parser.add_argument("--dataset", default="data/price_dataset.csv")
    parser.add_argument("--category", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--city", required=True)
    parser.add_argument("--quantity", required=True, type=float)
    parser.add_argument("--weight", required=True, type=float, help="Total weight in kg")
    parser.add_argument("--channel", choices=sorted(CHANNEL_COLUMNS), default="authorized")
    parser.add_argument("--unit", choices=["auto", "per_kg", "per_piece"], default="auto")
    parser.add_argument("--subcategory", default=None)
    parser.add_argument("--as-of-date", default=None, help="Optional quote date, e.g. 2026-09-05")
    args = parser.parse_args()

    engine = PriceEngine(args.dataset)
    result = engine.quote(
        QuoteRequest(
            category=args.category,
            state=args.state,
            city=args.city,
            quantity=args.quantity,
            total_weight_kg=args.weight,
            channel=args.channel,
            unit=args.unit,
            subcategory=args.subcategory,
            as_of_date=args.as_of_date,
        )
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
