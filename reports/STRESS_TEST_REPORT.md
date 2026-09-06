# E-Waste Price Engine Full Stress-Test Report

## Executive result

- Existing unit tests: **10/10 passed**.
- Price dataset rows: **1,116**.
- Supported categories: **8**.
- Supported city/state locations: **12**.
- Distinct category/subcategory combinations: **65**.
- Broad-category quote matrix: **288** requests.
- Exact-subcategory quote matrix: **2,340** requests.
- Fallback/alias requests: **48** requests.
- Total stress-test requests: **2,676**.
- Logic/coverage failures: **0**.
- Logic pass rate: **100.0%**.

> This is a software/coverage pass rate, **not real-world price prediction accuracy**. The dataset uses synthetic city/date expansion, so market accuracy requires independent live dealer/recycler quotes.

## What was validated

- Every one of the 8 categories at every supported city.
- All three channels: informal, mandi, and authorized recycler.
- Every available exact subcategory at every supported city.
- Correct city matching plus state and national fallbacks.
- Bangalore/Bengaluru, Bombay/Mumbai, Calcutta/Kolkata, and Delhi/Delhi NCR aliases.
- Latest-date selection and positive finite rates.
- Per-kg vs per-piece calculation formula.
- Recommended value remaining inside the displayed estimate range.
- Selected pricing channel matching the returned recommended rate.
- Expected informal ≤ mandi ≤ authorized channel ordering.
- Quote-quality score bounds, provenance ratio bounds, and synthetic-data warning.

## Broad-category quality by category (authorized channel)

| Category | City quotes | Pass | Avg quality | Avg relative IQR | High-spread cities | Direct evidence ratio |
|---|---:|---:|---:|---:|---:|---:|
| BATTERIES | 12 | 100% | 57.0/100 | 1.402 | 12 | 100.0% |
| CABLES_WIRES | 12 | 100% | 54.0/100 | 0.465 | 0 | 87.5% |
| CRT | 12 | 100% | 57.0/100 | 0.061 | 0 | 60.0% |
| LCD_LED | 12 | 100% | 57.0/100 | 0.184 | 0 | 83.3% |
| MOBILE_TABLETS | 12 | 100% | 57.0/100 | 2.318 | 12 | 100.0% |
| MOTORS | 12 | 100% | 54.0/100 | 0.660 | 0 | 50.0% |
| PCB | 12 | 100% | 57.0/100 | 1.652 | 12 | 100.0% |
| PLASTICS | 12 | 100% | 57.0/100 | 0.961 | 12 | 100.0% |

## Exact-subcategory quality

| Category | Subcategories | Quotes | Pass | Avg quality | High-spread quotes | Direct evidence ratio |
|---|---:|---:|---:|---:|---:|---:|
| BATTERIES | 9 | 108 | 100% | 80.0/100 | 0 | 100.0% |
| CABLES_WIRES | 8 | 96 | 100% | 78.8/100 | 0 | 87.5% |
| CRT | 5 | 60 | 100% | 76.0/100 | 0 | 60.0% |
| LCD_LED | 6 | 72 | 100% | 78.3/100 | 0 | 83.3% |
| MOBILE_TABLETS | 8 | 96 | 100% | 80.0/100 | 0 | 100.0% |
| MOTORS | 6 | 72 | 100% | 75.0/100 | 0 | 50.0% |
| PCB | 16 | 192 | 100% | 80.0/100 | 0 | 100.0% |
| PLASTICS | 7 | 84 | 100% | 80.0/100 | 0 | 100.0% |

## Main findings

- **PCB**: average broad-category quality 57.0/100; average relative IQR 1.652; 12/12 city quotes are high-spread.
- **MOBILE_TABLETS**: average broad-category quality 57.0/100; average relative IQR 2.318; 12/12 city quotes are high-spread.
- **BATTERIES**: average broad-category quality 57.0/100; average relative IQR 1.402; 12/12 city quotes are high-spread.
- **MOTORS**: average broad-category quality 54.0/100; average relative IQR 0.660; 0/12 city quotes are high-spread.
- **CABLES_WIRES**: average broad-category quality 54.0/100; average relative IQR 0.465; 0/12 city quotes are high-spread.
- **LCD_LED**: average broad-category quality 57.0/100; average relative IQR 0.184; 0/12 city quotes are high-spread.
- **CRT**: average broad-category quality 57.0/100; average relative IQR 0.061; 0/12 city quotes are high-spread.
- **PLASTICS**: average broad-category quality 57.0/100; average relative IQR 0.961; 12/12 city quotes are high-spread.

- Broad-category quotes are deliberately lower-confidence when the class contains materials with very different scrap values. Exact subcategory selection raises specificity and usually tightens the range.
- Every supported city has direct dataset coverage for all 8 top-level categories; therefore normal supported-city requests resolve at **city** level rather than falling back.
- Ghaziabad, Uttar Pradesh correctly resolves to **state-level** coverage because Lucknow is the only Uttar Pradesh city currently in the generated location table.
- Kochi, Kerala correctly resolves to **national fallback** because Kerala is not currently represented in the pricing dataset.

## Accuracy interpretation

The engine itself is deterministic, so there is no ML regression accuracy metric such as MAE/RMSE to report for the current version. This stress test verifies code correctness and data coverage. To measure actual rupee accuracy, collect an independent validation table of real quotes with columns such as category, subcategory, city, date, quoted rate, unit, and dealer/recycler source, then compare engine recommendations against those held-out observed rates using MAE, median absolute error, MAPE (where appropriate), and range coverage.

## Recommended next data improvements

1. Add **Ghaziabad** and other target deployment cities as direct observations rather than relying on state fallback.
2. Replace synthetic city/date expansion with repeated real dealer/recycler observations over time.
3. Prioritize exact subcategory/grade capture for PCB, mobile/tablet, batteries, cables, and motors because broad-category rates can vary substantially.
4. Keep source date and source identity so stale observations can be down-weighted or rejected.
5. Once enough independent historical observations exist, then evaluate whether CatBoost/XGBoost regression improves over this deterministic baseline.