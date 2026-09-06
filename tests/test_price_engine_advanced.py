import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from price_engine import PriceEngine, QuoteRequest


class PriceEngineAdvancedTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.tmpdir.name) / "price_dataset.csv"
        rows = [
            dict(
                vision_category="PCB", subcategory="Desktop PCB - Single Chip",
                location_state="Delhi NCR", location_city="Delhi", date_recorded="2026-09-05",
                unit_of_measure="per_kg", doorstep_informal_price_inr=500,
                wholesale_mandi_price_inr=600, authorized_recycler_offered_price_inr=700,
                market_range_min_inr=480, market_range_max_inr=750,
                material_evidence_level="DIRECT", material_source_name="Source A",
                is_synthetic=True, verification_status="Synthetic", data_source="test",
            ),
            dict(
                vision_category="PCB", subcategory="Laptop PCB - Server Board",
                location_state="Delhi NCR", location_city="Delhi", date_recorded="2026-09-05",
                unit_of_measure="per_kg", doorstep_informal_price_inr=1200,
                wholesale_mandi_price_inr=1500, authorized_recycler_offered_price_inr=1800,
                market_range_min_inr=1100, market_range_max_inr=1900,
                material_evidence_level="DIRECT_RANGE", material_source_name="Source B",
                is_synthetic=True, verification_status="Synthetic", data_source="test",
            ),
            dict(
                vision_category="PCB", subcategory="Low Grade PCB",
                location_state="Delhi NCR", location_city="Delhi", date_recorded="2026-09-05",
                unit_of_measure="per_kg", doorstep_informal_price_inr=100,
                wholesale_mandi_price_inr=120, authorized_recycler_offered_price_inr=140,
                market_range_min_inr=90, market_range_max_inr=150,
                material_evidence_level="PROXY", material_source_name="Source C",
                is_synthetic=True, verification_status="Synthetic", data_source="test",
            ),
        ]
        pd.DataFrame(rows).to_csv(self.csv_path, index=False)
        self.engine = PriceEngine(self.csv_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_delhi_alias_matches_delhi_ncr(self):
        result = self.engine.quote(QuoteRequest("PCB", "Delhi", "Delhi", 1, 2.0, as_of_date="2026-09-05"))
        self.assertEqual(result["match_level"], "city")
        self.assertIn("Delhi", result["matched_cities"])

    def test_exact_subcategory_improves_specificity(self):
        result = self.engine.quote(QuoteRequest(
            "PCB", "Delhi", "Delhi", 1, 2.0,
            subcategory="Desktop PCB - Single Chip", as_of_date="2026-09-05"
        ))
        self.assertTrue(result["subcategory_matched"])
        self.assertEqual(result["recommended_rate_inr"], 700.0)
        self.assertEqual(result["range_method"], "matched_subcategory_market_range")
        self.assertGreaterEqual(result["quote_quality_score"], 70)

    def test_missing_subcategory_raises_with_suggestions(self):
        with self.assertRaisesRegex(LookupError, "Close matches"):
            self.engine.quote(QuoteRequest(
                "PCB", "Delhi", "Delhi", 1, 2.0,
                subcategory="desktop single chip", as_of_date="2026-09-05"
            ))

    def test_broad_category_exposes_spread_and_warning(self):
        result = self.engine.quote(QuoteRequest("PCB", "Delhi", "Delhi", 1, 2.0, as_of_date="2026-09-05"))
        self.assertFalse(result["subcategory_matched"])
        self.assertGreater(result["market_rate_max_inr"], result["market_rate_min_inr"])
        self.assertTrue(any("Broad image category" in w for w in result["warnings"]))
        self.assertTrue(result["uses_synthetic_data"])

    def test_freshness_is_reported(self):
        result = self.engine.quote(QuoteRequest("PCB", "Delhi", "Delhi", 1, 2.0, as_of_date="2026-10-20"))
        self.assertEqual(result["freshness_days"], 45)
        self.assertEqual(result["freshness_band"], "aging")
        self.assertTrue(any("45 days old" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
