# Backend Integration Contract

## 1. Category source

The category is produced by the image-classification model.

Your current classifier labels can be passed directly:

- `Battery`
- `CRT`
- `LCD_LED`
- `Motors`
- `PCB`
- `Plastic`
- `Wires`

`PriceEngine` normalizes these to its canonical pricing categories internally.

The pricing engine additionally supports `MOBILE_TABLETS` if that class is added later.

## 2. User inputs

Collect these **after the user confirms/corrects the image prediction**:

```json
{
  "state": "Uttar Pradesh",
  "city": "Ghaziabad",
  "quantity": 5,
  "total_weight_kg": 12.5,
  "subcategory": null
}
```

`subcategory` is optional, but strongly recommended for heterogeneous materials
such as PCB, batteries, motors, plastics, and mobile/tablet scrap.

## 3. Call the engine

```python
from price_engine import PriceEngine, QuoteRequest

engine = PriceEngine("data/price_dataset.csv")

quote = engine.quote(
    QuoteRequest(
        category="PCB",
        state="Uttar Pradesh",
        city="Ghaziabad",
        quantity=5,
        total_weight_kg=12.5,
    )
)
```

## 4. Matching logic

The engine uses:

1. category
2. optional exact subcategory
3. exact state + city
4. state fallback
5. national fallback
6. latest available pricing snapshot
7. unit resolution (`per_kg` or `per_piece`)
8. median recommended rate and uncertainty range

## 5. Calculation

For `per_kg`:

```text
estimated value = total weight in kg × recommended rate
```

For `per_piece`:

```text
estimated value = quantity × recommended rate
```

Quantity is not multiplied again when the whole batch weight is already supplied.

## 6. Important production note

The current city/date price rows are synthetic scenario expansions from material
baselines. The engine is tested and deterministic, but the rupee quote is an
estimate. Replace/augment the pricing observations with independent current
kabadiwala/recycler market observations before presenting the output as a live
market quote.
