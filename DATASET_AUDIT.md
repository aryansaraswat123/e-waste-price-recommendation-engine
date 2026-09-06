# Pricing Dataset Audit

## Dataset status

- Price rows: **1,116**
- Material baseline rows: **65**
- Vision classes: **8**
- States/regions represented: **10**
- Cities represented: **12**
- Pricing snapshots: **5**
- Latest snapshot: **2026-09-05**
- Rows in latest snapshot: **780**
- Material evidence rows: **58 direct/direct-range, 7 proxy**
- Location/date expansion rows are **synthetic scenario estimates**, not independently observed live quotes.

## Latest authorized-rate dispersion by broad image class

| Vision class | Unit | Latest rows | Median | 10th pct | 90th pct | Relative IQR | Spread |
|---|---:|---:|---:|---:|---:|---:|---|
| BATTERIES | ₹/kg | 108 | ₹157.50 | ₹81.10 | ₹720.00 | 1.47 | high |
| CABLES_WIRES | ₹/kg | 96 | ₹547.50 | ₹357.50 | ₹747.50 | 0.49 | medium |
| CRT | ₹/piece | 60 | ₹180.00 | ₹140.00 | ₹205.00 | 0.14 | low |
| LCD_LED | ₹/kg | 72 | ₹27.00 | ₹22.00 | ₹31.00 | 0.20 | low |
| MOBILE_TABLETS | ₹/piece | 96 | ₹317.50 | ₹16.75 | ₹2,375.00 | 2.42 | high |
| MOTORS | ₹/kg | 72 | ₹61.50 | ₹51.00 | ₹209.50 | 0.88 | high |
| PCB | ₹/kg | 192 | ₹457.50 | ₹125.00 | ₹1,895.00 | 1.78 | high |
| PLASTICS | ₹/kg | 84 | ₹39.00 | ₹25.00 | ₹87.70 | 1.15 | high |

## Main findings

1. **PCB and MOBILE_TABLETS are too heterogeneous for a precise broad-class price.** Their subcategories span very different grades/device values. The engine therefore returns a wide uncertainty range and warns the caller when only the broad image class is available.
2. **BATTERIES, MOTORS and PLASTICS also benefit strongly from subcategory/grade selection.** Chemistry, copper content and resin type materially change value.
3. **CRT and LCD_LED are comparatively stable** in the current starter data, so broad-category quotes are more defensible for a prototype.
4. **Location coverage is intentionally limited.** For example, Ghaziabad is not a direct city row, so a Ghaziabad request currently falls back to the available Uttar Pradesh market (Lucknow).
5. **Do not train Random Forest/XGBoost on this generated price table as if it were real history.** It would mainly learn the configured generation factors. Keep the transparent pricing engine until independent historical market observations are collected.

## Engine behavior after upgrade

- city → state → national location fallback
- state/city aliases such as Delhi → Delhi NCR and Bangalore → Bengaluru
- newest available date selection
- `per_kg` vs `per_piece` formula safety
- median recommended rate
- robust 10th–90th percentile range for broad categories
- exact subcategory pricing when supplied
- subcategory typo suggestions instead of silently falling back
- freshness age/band
- internal spread (`relative_iqr`, `spread_level`)
- material evidence summary and source names
- synthetic-data warning
- 0–100 **quote quality score** (quality indicator, not a probability)