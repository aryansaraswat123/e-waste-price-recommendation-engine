# SIH E-Waste API Contract

Base URL after deployment:

```text
https://<render-service-name>.onrender.com
```

Authentication header for protected endpoints:

```text
X-API-Key: <private-api-key>
```

Do not expose the API key in frontend JavaScript. The website backend should call this API.

## Health

```http
GET /health
```

No API key required.

## Classify image

```http
POST /classify
Content-Type: multipart/form-data
X-API-Key: <private-api-key>
```

Form field:

```text
image: JPG/PNG/WEBP file, max 10 MB
```

Response:

```json
{
  "category": "Motors",
  "confidence": 0.9462,
  "confidence_percent": 94.62
}
```

Current model classes:

```text
Battery
CRT
LCD_LED
Motors
PCB
Plastic
Wires
```

## Price recommendation

```http
POST /price
Content-Type: application/json
X-API-Key: <private-api-key>
```

Request:

```json
{
  "category": "Motors",
  "state": "Uttar Pradesh",
  "city": "Ghaziabad",
  "quantity": 2,
  "total_weight_kg": 8.0,
  "confidence": 0.9462
}
```

Optional fields:

```json
{
  "subcategory": null,
  "channel": "authorized",
  "unit": "auto",
  "as_of_date": null
}
```

Response:

```json
{
  "classification": {
    "predicted_category": "Motors",
    "confidence": 0.9462
  },
  "pricing": {
    "category": "MOTORS",
    "recommended_rate_inr": 150.0,
    "unit": "per_kg",
    "estimated_value_inr": 1200.0,
    "estimated_value_min_inr": 1050.0,
    "estimated_value_max_inr": 1320.0,
    "match_level": "state",
    "quote_quality_score": 57,
    "warnings": []
  }
}
```

## Combined endpoint

```http
POST /predict-and-price
Content-Type: multipart/form-data
X-API-Key: <private-api-key>
```

Form fields:

```text
image: JPG/PNG/WEBP file
state: Uttar Pradesh
city: Ghaziabad
quantity: 2
total_weight_kg: 8.0
subcategory: optional
channel: authorized
unit: auto
as_of_date: optional
```

Recommended production flow:

```text
Frontend uploads image -> /classify -> user confirms or corrects category -> /price -> final estimate
```
