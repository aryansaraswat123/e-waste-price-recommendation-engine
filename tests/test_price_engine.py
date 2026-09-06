import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from price_engine import PriceEngine, QuoteRequest


class PriceEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.tmpdir.name) / "price_dataset.csv"
        rows = [
            # PCB - exact city, older date
            dict(vision_category="PCB", subcategory="Desktop Motherboard", location_state="Uttar Pradesh", location_city="Lucknow", date_recorded="2026-09-01", unit_of_measure="per_kg", doorstep_informal_price_inr=100, wholesale_mandi_price_inr=110, authorized_recycler_offered_price_inr=120, market_range_min_inr=95, market_range_max_inr=125, is_synthetic=True, verification_status="Synthetic", data_source="test"),
            # PCB - exact city, latest date, two rows -> median should be used
            dict(vision_category="PCB", subcategory="Desktop Motherboard", location_state="Uttar Pradesh", location_city="Lucknow", date_recorded="2026-09-05", unit_of_measure="per_kg", doorstep_informal_price_inr=110, wholesale_mandi_price_inr=120, authorized_recycler_offered_price_inr=130, market_range_min_inr=100, market_range_max_inr=140, is_synthetic=True, verification_status="Synthetic", data_source="test"),
            dict(vision_category="PCB", subcategory="Laptop Motherboard", location_state="Uttar Pradesh", location_city="Lucknow", date_recorded="2026-09-05", unit_of_measure="per_kg", doorstep_informal_price_inr=130, wholesale_mandi_price_inr=140, authorized_recycler_offered_price_inr=150, market_range_min_inr=120, market_range_max_inr=160, is_synthetic=True, verification_status="Synthetic", data_source="test"),
            # PCB - different city in same state
            dict(vision_category="PCB", subcategory="Desktop Motherboard", location_state="Uttar Pradesh", location_city="Kanpur", date_recorded="2026-09-05", unit_of_measure="per_kg", doorstep_informal_price_inr=90, wholesale_mandi_price_inr=100, authorized_recycler_offered_price_inr=110, market_range_min_inr=85, market_range_max_inr=115, is_synthetic=True, verification_status="Synthetic", data_source="test"),
            # Mobile - per piece only
            dict(vision_category="MOBILE_TABLETS", subcategory="Smartphone", location_state="Uttar Pradesh", location_city="Lucknow", date_recorded="2026-09-05", unit_of_measure="per_piece", doorstep_informal_price_inr=300, wholesale_mandi_price_inr=350, authorized_recycler_offered_price_inr=400, market_range_min_inr=280, market_range_max_inr=420, is_synthetic=True, verification_status="Synthetic", data_source="test"),
        ]
        pd.DataFrame(rows).to_csv(self.csv_path, index=False)
        self.engine = PriceEngine(self.csv_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_city_match_uses_latest_date_and_median(self):
        result = self.engine.quote(QuoteRequest("PCB", "Uttar Pradesh", "Lucknow", 5, 10.0))
        self.assertEqual(result["match_level"], "city")
        self.assertEqual(result["pricing_date"], "2026-09-05")
        self.assertEqual(result["recommended_rate_inr"], 140.0)
        self.assertEqual(result["estimated_value_inr"], 1400.0)
        self.assertEqual(result["data_points_used"], 2)

    def test_state_fallback(self):
        result = self.engine.quote(QuoteRequest("PCB", "Uttar Pradesh", "Agra", 2, 5.0))
        self.assertEqual(result["match_level"], "state")
        self.assertEqual(result["unit"], "per_kg")

    def test_national_fallback(self):
        result = self.engine.quote(QuoteRequest("PCB", "Rajasthan", "Jaipur", 2, 5.0))
        self.assertEqual(result["match_level"], "national")

    def test_per_piece_formula(self):
        result = self.engine.quote(QuoteRequest("MOBILE_TABLETS", "Uttar Pradesh", "Lucknow", 3, 1.2))
        self.assertEqual(result["unit"], "per_piece")
        self.assertEqual(result["estimated_value_inr"], 1200.0)

    def test_category_alias_lookup_error(self):
        with self.assertRaises(LookupError):
            self.engine.quote(QuoteRequest("Cables & Wires", "Uttar Pradesh", "Lucknow", 1, 1.0))


if __name__ == "__main__":
    unittest.main()
