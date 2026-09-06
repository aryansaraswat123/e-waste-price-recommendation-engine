from __future__ import annotations

import io
import os
import secrets
from pathlib import Path
from typing import Optional

import numpy as np
import tensorflow as tf
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from price_integration import recommend_price

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "best_e_waste_model.keras"
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

app = FastAPI(
    title="SIH E-Waste Classification & Pricing API",
    version="1.0.0",
    description=(
        "Classifies e-waste images into 7 categories and returns location-aware "
        "price recommendations. Use X-API-Key on protected endpoints."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

print(f"Loading model from {MODEL_PATH} ...")
model = tf.keras.models.load_model(MODEL_PATH)
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


def classify_raw_image(raw: bytes) -> dict:
    batch = preprocess_image(raw)
    predictions = model.predict(batch, verbose=0)
    predicted_index = int(np.argmax(predictions[0]))
    confidence = float(predictions[0][predicted_index])
    return {
        "category": CLASS_NAMES[predicted_index],
        "confidence": round(confidence, 6),
        "confidence_percent": round(confidence * 100, 2),
    }


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
        raise HTTPException(status_code=415, detail="Supported image types: JPEG, PNG, WEBP")

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Image file is empty")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 10 MB")

    return classify_raw_image(raw)


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


@app.post("/predict-and-price", dependencies=[Depends(require_api_key)])
async def predict_and_price(
    image: UploadFile = File(...),
    state: str = "",
    city: str = "",
    quantity: float = 1,
    total_weight_kg: float = 1,
    subcategory: Optional[str] = None,
    channel: str = "authorized",
    unit: str = "auto",
    as_of_date: Optional[str] = None,
) -> dict:
    classification = await classify(image)
    request = PriceRequest(
        category=classification["category"],
        state=state,
        city=city,
        quantity=quantity,
        total_weight_kg=total_weight_kg,
        confidence=classification["confidence"],
        subcategory=subcategory,
        channel=channel,
        unit=unit,
        as_of_date=as_of_date,
    )
    result = price(request)
    result["classification"].update(classification)
    return result


@app.get("/")
def root() -> dict:
    return {
        "service": "SIH E-Waste Classification & Pricing API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "protected_endpoints": ["POST /classify", "POST /price", "POST /predict-and-price"],
    }
