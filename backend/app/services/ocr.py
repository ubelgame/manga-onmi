"""
OCR and computer vision pipeline:
1. manga-ocr for Japanese text extraction
2. OpenCV contour analysis for bubble detection and shape classification
3. Shapely for polygon geometry (usable text area)
"""
import cv2
import numpy as np
from PIL import Image
from shapely.geometry import Polygon
import io
import uuid
import structlog

log = structlog.get_logger()

# ── Lazy-load manga-ocr (large model, load once per worker) ─────────────────
_mocr = None

def get_mocr():
    global _mocr
    if _mocr is None:
        from manga_ocr import MangaOcr
        _mocr = MangaOcr()
    return _mocr


# ── Bubble shape helpers ────────────────────────────────────────────────────

def classify_bubble_shape(contour: np.ndarray) -> str:
    """
    Returns one of: smooth_oval, rectangular, jagged, caption
    Based on:
      - solidity  (area / convex hull area)
      - circularity  (4π·area / perimeter²)
      - convexity defect count at depth > 10px
    """
    area = cv2.contourArea(contour)
    if area < 200:
        return "caption"

    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    solidity = area / hull_area if hull_area > 0 else 1.0

    perimeter = cv2.arcLength(contour, True)
    circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0

    # Convexity defects — deep notches → jagged SFX bubble
    hull_idx = cv2.convexHull(contour, returnPoints=False)
    defects = cv2.convexityDefects(contour, hull_idx) if len(hull_idx) >= 3 else None
    deep_defects = 0
    if defects is not None:
        for d in defects[:, 0]:
            depth = d[3] / 256.0
            if depth > 10:
                deep_defects += 1

    if deep_defects > 6 or solidity < 0.78:
        return "jagged"          # SFX / shout burst (like image_1.png)

    x, y, w, h = cv2.boundingRect(contour)
    aspect = w / h if h > 0 else 1.0
    if 0.8 < aspect < 1.6 and circularity < 0.6:
        return "rectangular"     # narration / caption box

    if circularity > 0.65:
        return "smooth_oval"     # standard dialogue (like image_0.png)

    return "smooth_oval"


def get_usable_area_polygon(contour: np.ndarray, inset_px: int = 14) -> list:
    """Shrink the bubble contour inward for safe text placement."""
    pts = contour.reshape(-1, 2).tolist()
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    inner = poly.buffer(-inset_px)
    if inner.is_empty:
        inner = poly
    return [list(c) for c in inner.exterior.coords]


def sample_bg_color(image_rgb: np.ndarray, contour: np.ndarray) -> tuple:
    """Sample the median color inside the bubble contour."""
    mask = np.zeros(image_rgb.shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
    pixels = image_rgb[mask == 255]
    if len(pixels) == 0:
        return (255, 255, 255)
    median = np.median(pixels, axis=0).astype(int)
    return tuple(median)


# ── Main OCR pipeline ───────────────────────────────────────────────────────

def apply_reading_order(blocks: list[dict]) -> list[dict]:
    """
    Sort OCR blocks in manga reading order: right-to-left within each row,
    top-to-bottom across rows. Blocks within ROW_TOLERANCE px of the same
    y-position are treated as the same row.
    """
    ROW_TOLERANCE = 60
    blocks.sort(key=lambda b: (
        b["bounding_box"]["y"] // ROW_TOLERANCE,
        -b["bounding_box"]["x"],   # negative = rightmost first
    ))
    for i, b in enumerate(blocks):
        b["reading_order_index"] = i
    return blocks


def detect_text_regions(gray: np.ndarray) -> list[np.ndarray]:
    """
    Simple but effective: threshold → find external contours → filter by size.
    In production, replace/supplement with CRAFT text detector for better recall.
    """
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(binary, kernel, iterations=4)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Filter: must be big enough to contain text
    return [c for c in contours if cv2.contourArea(c) > 500]


def ocr_page(image_bytes: bytes) -> list[dict]:
    """
    Full OCR pipeline for one manga page.
    Returns list of block dicts ready to insert into OCRBlock model.
    """
    mocr = get_mocr()

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    contours = detect_text_regions(gray)
    log.info("Detected text regions", count=len(contours))

    blocks = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        # Crop region for OCR
        crop_bgr = img_bgr[y:y+h, x:x+w]
        pil_crop = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))

        try:
            text = mocr(pil_crop)
        except Exception as e:
            log.warning("MangaOCR failed", error=str(e))
            text = ""

        if not text.strip():
            continue

        shape = classify_bubble_shape(contour)
        usable = get_usable_area_polygon(contour)
        bg_rgb = sample_bg_color(img_rgb, contour)
        bg_hex = "#{:02X}{:02X}{:02X}".format(*bg_rgb)
        is_dark = (0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]) < 128

        # Map shape + darkness to font suggestion
        font_map = {
            "jagged": "Bangers",
            "rectangular": "Manga Temple",
            "thought": "Anime Ace",
            "smooth_oval": "Anime Ace",
            "caption": "Manga Temple",
        }
        suggested_font = font_map.get(shape, "Anime Ace")

        # Detect SFX: mostly katakana (Unicode range U+30A0-U+30FF)
        katakana_ratio = sum(1 for c in text if "\u30A0" <= c <= "\u30FF") / max(len(text), 1)
        is_sfx = shape == "jagged" or katakana_ratio > 0.5

        blocks.append({
            "id": str(uuid.uuid4()),
            "raw_jp_text": text,
            "bounding_box": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
            "confidence": 0.85,  # manga-ocr doesn't expose confidence; assume high
            "is_sfx": is_sfx,
            "bubble_shape": shape,
            "contour_points": contour.reshape(-1, 2).tolist(),
            "usable_area_polygon": usable,
            "bg_color_hex": bg_hex,
            "is_dark_bg": is_dark,
            "suggested_font": suggested_font,
        })

    return apply_reading_order(blocks)
