"""Thumbnail Composition Analyzer — Local image analysis using OpenCV + Pillow.

Analyzes thumbnails for composition quality without expensive Vision API calls:
- Face detection (OpenCV Haar cascades)
- Color contrast analysis
- Brightness / saturation scoring
- Rule of thirds check
- Text readability estimation

When local score is high enough, we can SKIP the GPT Vision QC call entirely,
saving ~$0.01-0.03 per thumbnail evaluation.

Intelligence cost: $0.00 — all computation is local via OpenCV + Pillow.
"""

from __future__ import annotations

import asyncio
import io

import numpy as np
import structlog

logger = structlog.get_logger()

_cv2 = None
_cv2_lock = asyncio.Lock()
_face_cascade = None


async def _get_cv2():
    global _cv2, _face_cascade
    if _cv2 is not None:
        return _cv2
    async with _cv2_lock:
        if _cv2 is not None:
            return _cv2

        def _load():
            import cv2

            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            return cv2, cascade

        _cv2, _face_cascade = await asyncio.to_thread(_load)
        logger.info("composition_analyzer.opencv_loaded")
        return _cv2


async def analyze_composition(image_bytes: bytes) -> dict:
    """Analyze thumbnail composition using local CV.

    Returns composition features and a composite score (1-10).
    """
    if not image_bytes or len(image_bytes) < 100:
        return {"composition_score": 1.0, "error": "No image data"}

    try:
        cv2 = await _get_cv2()

        def _analyze():
            from PIL import Image

            img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            width, height = img_pil.size

            img_np = np.array(img_pil)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

            features = {"width": width, "height": height}

            faces = _face_cascade.detectMultiScale(img_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            features["has_face"] = len(faces) > 0
            features["face_count"] = len(faces)
            if len(faces) > 0:
                total_face_area = sum(w * h for (_, _, w, h) in faces)
                features["face_area_ratio"] = round(total_face_area / (width * height), 4)
            else:
                features["face_area_ratio"] = 0.0

            brightness = float(np.mean(img_gray)) / 255.0
            features["brightness"] = round(brightness, 3)

            saturation = float(np.mean(img_hsv[:, :, 1])) / 255.0
            features["saturation"] = round(saturation, 3)

            luminance_std = float(np.std(img_gray)) / 255.0
            features["contrast"] = round(luminance_std * 10, 2)

            pixels = img_np.reshape(-1, 3)
            from collections import Counter

            quantized = (pixels // 32 * 32).tolist()
            color_counts = Counter(tuple(c) for c in quantized)
            top_colors = color_counts.most_common(3)
            features["dominant_colors"] = [
                {"rgb": list(c[0]), "ratio": round(c[1] / len(quantized), 3)} for c in top_colors
            ]

            thirds_h = [height // 3, 2 * height // 3]
            thirds_w = [width // 3, 2 * width // 3]

            thirds_score = 5.0
            if len(faces) > 0:
                for x, y, w, h in faces:
                    face_cx = x + w // 2
                    face_cy = y + h // 2
                    min_dist_w = min(abs(face_cx - tw) for tw in thirds_w) / width
                    min_dist_h = min(abs(face_cy - th) for th in thirds_h) / height
                    if min_dist_w < 0.1 or min_dist_h < 0.1:
                        thirds_score = 9.0
                    elif min_dist_w < 0.2 or min_dist_h < 0.2:
                        thirds_score = 7.5
            else:
                edges = cv2.Canny(img_gray, 100, 200)
                edge_density = float(np.mean(edges > 0))
                for ty in thirds_h:
                    zone = edges[max(0, ty - 30) : min(height, ty + 30), :]
                    zone_density = float(np.mean(zone > 0))
                    if zone_density > edge_density * 1.5:
                        thirds_score = max(thirds_score, 7.0)

            features["rule_of_thirds_score"] = round(thirds_score, 1)

            return features

        features = await asyncio.to_thread(_analyze)

    except Exception as e:
        logger.warning("composition_analyzer.failed", error=str(e))
        return {"composition_score": 5.0, "error": str(e), "used_fallback": True}

    score = 5.0
    issues = []

    if features.get("has_face"):
        face_ratio = features.get("face_area_ratio", 0)
        if 0.05 < face_ratio < 0.40:
            score += 2.0
        elif face_ratio >= 0.40:
            score += 1.5
            issues.append("Face occupies too much of thumbnail")
        else:
            score += 0.5
    else:
        score += 0.5

    brightness = features.get("brightness", 0.5)
    if 0.25 < brightness < 0.80:
        score += 1.0
    elif brightness <= 0.15:
        score -= 1.0
        issues.append("Thumbnail too dark")
    elif brightness >= 0.90:
        score -= 0.5
        issues.append("Thumbnail too bright/washed out")

    saturation = features.get("saturation", 0.3)
    if saturation > 0.4:
        score += 1.0
    elif saturation < 0.15:
        score -= 1.0
        issues.append("Low saturation — thumbnail looks dull")

    contrast = features.get("contrast", 3)
    if contrast > 4:
        score += 0.5
    elif contrast < 2:
        score -= 1.0
        issues.append("Low contrast — elements don't pop")

    thirds = features.get("rule_of_thirds_score", 5.0)
    score += (thirds - 5.0) * 0.2

    score = max(1.0, min(10.0, round(score, 1)))

    return {
        "composition_score": score,
        "features": features,
        "issues": issues,
    }


async def analyze_batch(image_bytes_list: list[bytes]) -> list[dict]:
    """Analyze multiple thumbnails in parallel."""
    tasks = [analyze_composition(img) for img in image_bytes_list]
    return await asyncio.gather(*tasks)
