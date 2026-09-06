"""Example bridge between the image classifier and the pricing engine.

The current 7-class image classifier can output labels such as:
Battery, CRT, LCD_LED, Motors, PCB, Plastic, Wires.

PriceEngine already accepts those labels through its category-alias mapping.
"""

from pathlib import Path
from typing import Any, Dict

from price_engine import PriceEngine, QuoteRequest


DATASET_PATH = Path(__file__).resolve().parent / "data" / "price_dataset.csv"
engine = PriceEngine(DATASET_PATH)


def recommend_price(
    classifier_result: Dict[str, Any],
    user_input: Dict[str, Any],
) -> Dict[str, Any]:
    """Return one combined classification + pricing response.

    classifier_result example:
        {"category": "PCB", "confidence": 0.88}

    user_input example:
        {
            "state": "Uttar Pradesh",
            "city": "Ghaziabad",
            "quantity": 5,
            "total_weight_kg": 12.5,
            "subcategory": None
        }
    """
    category = classifier_result["category"]

    quote = engine.quote(
        QuoteRequest(
            category=category,
            state=user_input["state"],
            city=user_input["city"],
            quantity=float(user_input["quantity"]),
            total_weight_kg=float(user_input["total_weight_kg"]),
            subcategory=user_input.get("subcategory"),
            channel=user_input.get("channel", "authorized"),
            unit=user_input.get("unit", "auto"),
            as_of_date=user_input.get("as_of_date"),
        )
    )

    return {
        "classification": {
            "predicted_category": category,
            "confidence": classifier_result.get("confidence"),
        },
        "pricing": quote,
    }


if __name__ == "__main__":
    classifier_result = {
        "category": "PCB",
        "confidence": 0.88,
    }

    user_input = {
        "state": "Uttar Pradesh",
        "city": "Ghaziabad",
        "quantity": 5,
        "total_weight_kg": 12.5,
    }

    result = recommend_price(classifier_result, user_input)

    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
