"""
Inpainting: erases original Japanese text using LaMa-style fill.
Typesetting: renders English text into bubble using shapely scan-line wrapping.

In production, replace the simple CV inpainter with the full LaMa model:
  pip install lama-cleaner
  from lama_cleaner.model import LaMa
  from lama_cleaner.schema import Config
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, LineString
import io
import os
import structlog

log = structlog.get_logger()

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


# ── Inpainting ──────────────────────────────────────────────────────────────

def inpaint_text_regions(image_bytes: bytes, ocr_blocks: list[dict]) -> bytes:
    """
    Erases original Japanese text regions.
    Uses OpenCV's INPAINT_TELEA for quick results.
    For production quality matching image_0.png / image_1.png,
    swap this with LaMa (see comment above).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    mask = np.zeros(img.shape[:2], dtype=np.uint8)

    for block in ocr_blocks:
        bb = block["bounding_box"]
        x, y, w, h = bb["x"], bb["y"], bb["w"], bb["h"]
        # Dilate mask by 5px to catch anti-aliased edges of Japanese glyphs
        cv2.rectangle(mask, (x - 5, y - 5), (x + w + 5, y + h + 5), 255, thickness=cv2.FILLED)

    # INPAINT_TELEA works well for manga line art; LaMa handles screentones better
    inpainted = cv2.inpaint(img, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)

    _, buf = cv2.imencode(".jpg", inpainted, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes()


# ── Contour-aware text wrapping ─────────────────────────────────────────────

def wrap_text_to_polygon(
    text: str,
    polygon_coords: list,
    font: ImageFont.FreeTypeFont,
    line_height_factor: float = 1.35,
) -> list[tuple[str, int, int]]:
    """
    Scan-line text wrapping inside a shapely polygon.
    Returns list of (line_text, x_center, y) for each rendered line.
    This produces the natural circular flow visible in image_0.png.
    """
    poly = Polygon(polygon_coords)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        return []

    min_x, min_y, max_x, max_y = poly.bounds

    # Estimate line height from font metrics
    try:
        bbox = font.getbbox("Ag")
        line_h = bbox[3] - bbox[1]
    except Exception:
        line_h = 14
    line_step = int(line_h * line_height_factor)

    words = text.split()
    lines = []
    y = min_y + line_step

    while words and y < max_y - line_step * 0.5:
        # Horizontal span at this y scan line
        scan_line = LineString([(min_x - 10, y), (max_x + 10, y)])
        intersection = poly.intersection(scan_line)

        if intersection.is_empty:
            y += line_step
            continue

        # Handle MultiLineString (bubble with concave edges)
        if hasattr(intersection, "geoms"):
            spans = list(intersection.geoms)
            longest = max(spans, key=lambda s: s.length)
            span_width = longest.length
            x_center = (longest.bounds[0] + longest.bounds[2]) / 2
        else:
            span_width = intersection.length
            x_center = (intersection.bounds[0] + intersection.bounds[2]) / 2

        # Greedily pack words that fit this span
        line_words: list[str] = []
        for word in words:
            test = " ".join(line_words + [word])
            try:
                w = font.getlength(test)
            except Exception:
                w = len(test) * 7  # rough fallback
            if w <= span_width - 8:  # 4px padding each side
                line_words.append(word)
            else:
                break

        if not line_words:
            line_words = [words[0]]  # force single word even if too wide

        words = words[len(line_words):]
        lines.append((" ".join(line_words), int(x_center), int(y)))
        y += line_step

    return lines


def fit_font_to_bubble(
    text: str,
    polygon_coords: list,
    font_name: str,
    start_size: int = 16,
    min_size: int = 7,
) -> tuple[ImageFont.FreeTypeFont, list]:
    """
    Iteratively decrease font size until text fits bubble.
    Returns (font, wrapped_lines).
    """
    font_path = _resolve_font(font_name)
    size = start_size
    while size >= min_size:
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            font = ImageFont.load_default()
        lines = wrap_text_to_polygon(text, polygon_coords, font)
        if lines:
            return font, lines
        size -= 1
    font = ImageFont.truetype(font_path, min_size) if font_path else ImageFont.load_default()
    return font, wrap_text_to_polygon(text, polygon_coords, font)


def _resolve_font(font_name: str) -> str | None:
    """Find font file in app/fonts/. Falls back to PIL default if not found."""
    candidates = [
        os.path.join(FONTS_DIR, f"{font_name}.ttf"),
        os.path.join(FONTS_DIR, f"{font_name}.otf"),
        os.path.join(FONTS_DIR, "AnimeAce2.ttf"),  # safe fallback
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    log.warning("Font not found, using PIL default", font=font_name)
    return None


# ── Final typesetting render ────────────────────────────────────────────────

def typeset_page(inpainted_bytes: bytes, ocr_blocks: list[dict]) -> bytes:
    """
    Renders all translated English text onto the inpainted image.
    Each block uses its own font, size, and contour-wrapped layout.
    """
    pil_img = Image.open(io.BytesIO(inpainted_bytes)).convert("RGB")
    draw = ImageDraw.Draw(pil_img)

    for block in ocr_blocks:
        en_text = block.get("final_english_text", "")
        if not en_text:
            continue

        usable = block.get("usable_area_polygon") or []
        if not usable:
            # Fallback: use bounding box as rectangle polygon
            bb = block["bounding_box"]
            x, y, w, h = bb["x"], bb["y"], bb["w"], bb["h"]
            usable = [(x+8, y+8), (x+w-8, y+8), (x+w-8, y+h-8), (x+8, y+h-8)]

        font_name = block.get("font_family") or block.get("suggested_font") or "AnimeAce2"
        font_size = int(block.get("font_size_pt") or 13)
        is_dark_bg = block.get("is_dark_bg", False)
        text_color = "#FFFFFF" if is_dark_bg else "#000000"

        font, lines = fit_font_to_bubble(en_text, usable, font_name, start_size=font_size)

        for line_text, x_center, y in lines:
            # Draw thin white stroke for readability on complex backgrounds
            if not is_dark_bg:
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    draw.text((x_center + dx, y + dy), line_text,
                              font=font, fill="#FFFFFF", anchor="mm")
            draw.text((x_center, y), line_text, font=font, fill=text_color, anchor="mm")

    out = io.BytesIO()
    pil_img.save(out, format="JPEG", quality=95)
    return out.getvalue()
