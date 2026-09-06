from __future__ import annotations

import base64
import io
import os
import secrets
from pathlib import Path
from typing import Optional

import numpy as np
import tensorflow as tf
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from price_integration import recommend_price

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "best_e_waste_model.keras"
MODEL_PARTS_DIR = BASE_DIR / "model_parts"
IMAGE_SIZE = (256, 256)
CLASS_NAMES = [
    "Battery",
    "CRT",
    "LCD_LED",
    "Motors",
    "PCB",
    "Plastic",
    "Wires",
]
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def ensure_model_file() -> Path:
    """Reconstruct the Keras model from Git-friendly base64 chunks when needed."""
    if MODEL_PATH.exists():
        return MODEL_PATH

    parts = sorted(MODEL_PARTS_DIR.glob("part_*.b64"))
    if not parts:
        raise RuntimeError(
            "Model file is missing and no model_parts/part_*.b64 files were found."
        )

    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    MODEL_PATH.write_bytes(base64.b64decode(encoded, validate=True))
    return MODEL_PATH


app = FastAPI(
    title="SIH E-Waste Classification & Pricing API",
    version="1.0.0",
    description=(
        "Classifies e-waste images into 7 categories and returns location-aware "
        "price recommendations. Use X-API-Key on protected endpoints."
    ),
)

_resolved_model_path = ensure_model_file()
print(f"Loading model from {_resolved_model_path} ...")
model = tf.keras.models.load_model(_resolved_model_path)
print("Model loaded successfully.")


def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="API key is not configured on the server")
    if not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


def preprocess_image(raw: bytes) -> np.ndarray:
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or unsupported image file") from exc

    image = image.resize(IMAGE_SIZE, Image.Resampling.BILINEAR)
    arr = np.asarray(image, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


class PriceRequest(BaseModel):
    category: str
    state: str = Field(min_length=1)
    city: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    total_weight_kg: float = Field(gt=0)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    subcategory: Optional[str] = None
    channel: str = "authorized"
    unit: str = "auto"
    as_of_date: Optional[str] = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "classes": CLASS_NAMES,
    }


@app.post("/classify", dependencies=[Depends(require_api_key)])
async def classify(image: UploadFile = File(...)) -> dict:
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Supported image types: JPEG, PNG, WEBP",
        )

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Image file is empty")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 10 MB")

    batch = preprocess_image(raw)
    predictions = model.predict(batch, verbose=0)
    predicted_index = int(np.argmax(predictions[0]))
    confidence = float(predictions[0][predicted_index])

    return {
        "category": CLASS_NAMES[predicted_index],
        "confidence": round(confidence, 6),
        "confidence_percent": round(confidence * 100, 2),
    }


@app.post("/price", dependencies=[Depends(require_api_key)])
def price(request: PriceRequest) -> dict:
    classifier_result = {
        "category": request.category,
        "confidence": request.confidence,
    }
    user_input = {
        "state": request.state,
        "city": request.city,
        "quantity": request.quantity,
        "total_weight_kg": request.total_weight_kg,
        "subcategory": request.subcategory,
        "channel": request.channel,
        "unit": request.unit,
        "as_of_date": request.as_of_date,
    }

    try:
        return recommend_price(classifier_result, user_input)
    except (ValueError, LookupError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def root() -> dict:
    return {
        "service": "SIH E-Waste Classification & Pricing API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "protected_endpoints": ["POST /classify", "POST /price"],
    }
