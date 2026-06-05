import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base
import enum


class ProcessingStatus(str, enum.Enum):
    queued = "queued"
    scraping = "scraping"
    ocr = "ocr"
    translating = "translating"
    inpainting = "inpainting"
    typesetting = "typesetting"
    done = "done"
    failed = "failed"


class BubbleShape(str, enum.Enum):
    smooth_oval = "smooth_oval"
    rectangular = "rectangular"
    jagged = "jagged"
    thought = "thought"
    caption = "caption"


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_name: Mapped[str] = mapped_column(String(255), default="Unknown Series")
    chapter_number: Mapped[str] = mapped_column(String(50), default="0")
    source_url: Mapped[str] = mapped_column(Text)
    status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus), default=ProcessingStatus.queued
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pages: Mapped[list["MangaPage"]] = relationship("MangaPage", back_populates="chapter")


class MangaPage(Base):
    __tablename__ = "manga_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(Text, nullable=True)
    raw_image_s3_key: Mapped[str] = mapped_column(Text, nullable=True)
    inpainted_s3_key: Mapped[str] = mapped_column(Text, nullable=True)
    final_s3_key: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus), default=ProcessingStatus.queued
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="pages")
    ocr_blocks: Mapped[list["OCRBlock"]] = relationship("OCRBlock", back_populates="page")


class OCRBlock(Base):
    __tablename__ = "ocr_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("manga_pages.id"))
    raw_jp_text: Mapped[str] = mapped_column(Text)
    bounding_box: Mapped[dict] = mapped_column(JSONB)          # {x, y, w, h}
    confidence: Mapped[float] = mapped_column(Float)
    reading_order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_sfx: Mapped[bool] = mapped_column(Boolean, default=False)

    bubble_shape: Mapped[str] = mapped_column(String(50), nullable=True)
    contour_points: Mapped[list] = mapped_column(JSONB, nullable=True)
    usable_area_polygon: Mapped[list] = mapped_column(JSONB, nullable=True)
    bg_color_hex: Mapped[str] = mapped_column(String(7), nullable=True)
    suggested_font: Mapped[str] = mapped_column(String(100), nullable=True)

    # Translation result
    final_english_text: Mapped[str] = mapped_column(Text, nullable=True)
    tone_label: Mapped[str] = mapped_column(String(50), nullable=True)
    tl_note: Mapped[str] = mapped_column(Text, nullable=True)
    font_family: Mapped[str] = mapped_column(String(100), nullable=True)
    font_size_pt: Mapped[float] = mapped_column(Float, nullable=True)

    page: Mapped["MangaPage"] = relationship("MangaPage", back_populates="ocr_blocks")


class GlossaryTerm(Base):
    """Character names and series-specific terminology."""
    __tablename__ = "glossary_terms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id"))
    japanese_term: Mapped[str] = mapped_column(String(255))
    english_term: Mapped[str] = mapped_column(String(255))
    term_type: Mapped[str] = mapped_column(String(50), default="general")  # character, location, technique
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
