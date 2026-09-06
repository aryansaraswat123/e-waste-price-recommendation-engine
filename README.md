# E-Waste Price Recommendation Engine

Location-aware, explainable price calculation module for an e-waste classification application.

> **Module boundary:** the ML image classifier identifies the e-waste category.  
> This repository receives that category plus user-entered location, quantity and weight, then returns an estimated scrap-value recommendation.

## End-to-end flow

```text
Phone camera / gallery
        ↓
ML image classifier
        ↓
Predicted category + confidence
        ↓
User confirms or corrects category
        ↓
User enters:
• State
• City
• Quantity
• Total weight
• Optional subcategory/grade
        ↓
PRICE ENGINE
        ↓
Category normalization
        ↓
Category / optional subcategory filtering
        ↓
City match
   ↓ unavailable
State fallback
   ↓ unavailable
National fallback
        ↓
Latest available price snapshot
        ↓
Resolve per_kg / per_piece
        ↓
Median recommended rate
+ market range
+ freshness
+ spread
+ provenance
        ↓
Final estimated scrap value
```

## Current classifier → pricing-engine compatibility

Your current image model can send its labels directly:

| Classifier label | Pricing category |
|---|---|
| `Battery` | `BATTERIES` |
| `CRT` | `CRT` |
| `LCD_LED` | `LCD_LED` |
| `Motors` | `MOTORS` |
| `PCB` | `PCB` |
| `Plastic` | `PLASTICS` |
| `Wires` | `CABLES_WIRES` |

The engine also supports `MOBILE_TABLETS` for future expansion.

## Repository structure

```text
e-waste-price-recommendation-engine/
├── data/
│   ├── material_dataset.csv
│   └── price_dataset.csv
├── tests/
│   ├── test_price_engine.py
│   └── test_price_engine_advanced.py
├── price_engine.py
├── generate_price_dataset.py
├── integration_example.py
├── example_quotes.json
├── DATASET_AUDIT.md
├── INTEGRATION.md
├── requirements.txt
├── .gitignore
└── README.md
```

## Install

```bash
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

### macOS / Linux

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Run all tests

```bash
pytest -q
```

Current packaged version: **10 automated tests pass**.

## Basic Python usage

```python
from price_engine import PriceEngine, QuoteRequest

engine = PriceEngine("data/price_dataset.csv")

result = engine.quote(
    QuoteRequest(
        category="PCB",              # from classifier
        state="Uttar Pradesh",       # user input
        city="Ghaziabad",            # user input
        quantity=5,                  # user input
        total_weight_kg=12.5,        # user input
    )
)

print(result)
```

For a complete classifier → pricing bridge, see [`integration_example.py`](integration_example.py).

## CLI example

```bash
python price_engine.py \
  --dataset data/price_dataset.csv \
  --category PCB \
  --state "Uttar Pradesh" \
  --city Ghaziabad \
  --quantity 5 \
  --weight 12.5
```

## Optional subcategory for a stronger quote

Broad categories can contain materials with very different values. When the application knows the subtype, pass it:

```python
QuoteRequest(
    category="PCB",
    subcategory="Desktop PCB - Single Chip",
    state="Uttar Pradesh",
    city="Lucknow",
    quantity=5,
    total_weight_kg=12.5,
)
```

This is especially useful for:

- PCB
- batteries
- motors
- plastics
- mobile/tablet scrap

## Calculation rules

### Weight-based material

```text
estimated value = total_weight_kg × recommended_rate_inr
```

### Piece-based material

```text
estimated value = quantity × recommended_rate_inr
```

The engine does **not** multiply by quantity again when total weight already represents the full batch.

## Location fallback

The engine searches in this order:

1. exact category + state + city
2. category + state
3. category nationally

The returned response includes `match_level` (`city`, `state`, or `national`) so the UI can explain the quote.

## What the engine returns

The response includes, among other fields:

- normalized category
- requested/matched subcategory
- match level
- matched city/state
- pricing date
- freshness
- selected pricing unit
- informal/kabadiwala rate
- mandi/wholesale rate
- authorized recycler rate
- recommended rate
- uncertainty range
- estimated minimum / recommended / maximum value
- data-points used
- spread level
- evidence/source information
- quote-quality score
- warnings

See [`example_quotes.json`](example_quotes.json) for complete examples.

## Regenerate `price_dataset.csv`

```bash
python generate_price_dataset.py \
  --materials data/material_dataset.csv \
  --output data/price_dataset.csv
```

## Dataset status

The current packaged pricing data contains:

- **65** material baseline rows
- **1,116** generated pricing rows
- **8** canonical pricing categories
- **12** represented cities
- `per_kg` and `per_piece` pricing

See [`DATASET_AUDIT.md`](DATASET_AUDIT.md) for the detailed audit.

## Important limitation

The current location/date pricing table is a **prototype scenario dataset** generated from material baselines plus configured location/date factors.

Therefore:

- the **engine logic is deterministic and tested**
- the output is a **price recommendation / estimate**
- it is **not an ML price-regression model**
- it should **not be presented as a guaranteed live market quote**
- production deployment should replace or augment synthetic scenario rows with independently observed current kabadiwala/recycler prices

## Integration

Read [`INTEGRATION.md`](INTEGRATION.md) for the exact backend contract between:

```text
Image classifier → user confirmation/input → PriceEngine → final UI
```

## Suggested GitHub repository name

```text
e-waste-price-recommendation-engine
```

## Architecture diagram

The end-to-end application flow is documented in [`docs/system_architecture.png`](docs/system_architecture.png). The pricing repository itself starts at the confirmed image-classification category and user-entered pricing inputs.

## Validation status

- 10 automated unit/integration tests pass.
- A larger stress-test matrix was run across all supported categories, cities, subcategories, pricing channels, and fallback cases.
- See [`reports/STRESS_TEST_REPORT.md`](reports/STRESS_TEST_REPORT.md) for the test summary when included in this repository snapshot.

## Important data limitation

The current price dataset is a prototype/research dataset. The pricing engine logic is tested, but production deployment should continuously replace or augment generated location/date observations with independent current quotes from kabadiwalas, scrap mandis, and authorized recyclers.
