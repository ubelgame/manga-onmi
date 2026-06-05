from pydantic import BaseModel, HttpUrl
from typing import Optional
import uuid
from datetime import datetime
from app.models.db_models import ProcessingStatus, BubbleShape


# ── Request schemas ─────────────────────────────────────────────────────────

class ChapterSubmit(BaseModel):
    source_url: str
    series_name: str = "Unknown Series"
    chapter_number: str = "1"

class TranslationOverride(BaseModel):
    english_text: str
    tl_note: Optional[str] = None


# ── Response schemas ────────────────────────────────────────────────────────

class BoundingBox(BaseModel):
    x: int; y: int; w: int; h: int

class OCRBlockOut(BaseModel):
    id: uuid.UUID
    raw_jp_text: str
    bounding_box: dict
    confidence: float
    reading_order_index: int
    is_sfx: bool
    bubble_shape: Optional[str]
    final_english_text: Optional[str]
    tone_label: Optional[str]
    tl_note: Optional[str]
    font_family: Optional[str]
    font_size_pt: Optional[float]

    class Config:
        from_attributes = True

class MangaPageOut(BaseModel):
    id: uuid.UUID
    chapter_id: uuid.UUID
    page_number: int
    status: ProcessingStatus
    raw_image_s3_key: Optional[str]
    inpainted_s3_key: Optional[str]
    final_s3_key: Optional[str]
    error_message: Optional[str]
    ocr_blocks: list[OCRBlockOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChapterOut(BaseModel):
    id: uuid.UUID
    series_name: str
    chapter_number: str
    source_url: str
    status: ProcessingStatus
    created_at: datetime
    page_count: int = 0

    class Config:
        from_attributes = True

class PresignedUrlOut(BaseModel):
    url: str
    expires_in: int = 3600

class GlossaryTermOut(BaseModel):
    id: uuid.UUID
    japanese_term: str
    english_term: str
    term_type: str

    class Config:
        from_attributes = True
