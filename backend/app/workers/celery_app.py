"""
Celery task definitions.
Pipeline: scrape_chapter → ocr_page → translate_page → typeset_page

Each task updates the MangaPage status in Postgres so the frontend
can show live progress via WebSocket.
"""
import asyncio
import uuid
from celery import Celery
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session
import structlog

from app.core.config import get_settings
from app.models.db_models import Chapter, MangaPage, OCRBlock, GlossaryTerm, ProcessingStatus
from app.services import scraper as scraper_svc, storage, ocr as ocr_svc
from app.services.translation import translate_block, build_context_text, select_font_for_block
from app.services.typesetter import inpaint_text_regions, typeset_page

settings = get_settings()
log = structlog.get_logger()

# Sync engine for Celery workers (Celery is not async)
# sync_database_url handles Railway postgres:// → psycopg2-compatible URL
_sync_url = settings.sync_database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
sync_engine = create_engine(_sync_url, pool_pre_ping=True)

celery_app = Celery(
    "manga_omni",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


def _set_page_status(session: Session, page_id: str, status: ProcessingStatus, error: str = None):
    from datetime import datetime
    vals = {"status": status, "updated_at": datetime.utcnow()}
    if error:
        vals["error_message"] = error
    session.execute(
        update(MangaPage).where(MangaPage.id == uuid.UUID(page_id)).values(**vals)
    )
    session.commit()


# ── Task 1: Scrape chapter ──────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, queue="scraper", name="tasks.scrape_chapter")
def task_scrape_chapter(self, chapter_id: str):
    log.info("Scraping chapter", chapter_id=chapter_id)
    with Session(sync_engine) as session:
        chapter = session.get(Chapter, uuid.UUID(chapter_id))
        if not chapter:
            return {"error": "Chapter not found"}

        chapter.status = ProcessingStatus.scraping
        session.commit()

        try:
            page_data = asyncio.run(scraper_svc.scrape_and_store_chapter(chapter.source_url))
        except Exception as exc:
            chapter.status = ProcessingStatus.failed
            session.commit()
            raise self.retry(exc=exc, countdown=60)

        for pd in page_data:
            page = MangaPage(
                chapter_id=chapter.id,
                page_number=pd["page_number"],
                source_url=pd["source_url"],
                raw_image_s3_key=pd["s3_key"],
                status=ProcessingStatus.queued,
            )
            session.add(page)
        session.commit()

        chapter.status = ProcessingStatus.ocr
        session.commit()

        # Enqueue OCR for each page
        pages = session.execute(
            select(MangaPage).where(MangaPage.chapter_id == chapter.id)
        ).scalars().all()
        for page in pages:
            task_ocr_page.apply_async(args=[str(page.id)], queue="ocr")

    return {"chapter_id": chapter_id, "pages_scraped": len(page_data)}


# ── Task 2: OCR a single page ───────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2, queue="ocr", name="tasks.ocr_page")
def task_ocr_page(self, page_id: str):
    log.info("OCR page", page_id=page_id)
    with Session(sync_engine) as session:
        page = session.get(MangaPage, uuid.UUID(page_id))
        if not page:
            return

        _set_page_status(session, page_id, ProcessingStatus.ocr)

        try:
            image_bytes = storage.download_image_bytes(page.raw_image_s3_key)
            blocks = ocr_svc.ocr_page(image_bytes)
        except Exception as exc:
            _set_page_status(session, page_id, ProcessingStatus.failed, str(exc))
            raise self.retry(exc=exc, countdown=30)

        for b in blocks:
            ocr_block = OCRBlock(
                id=uuid.UUID(b["id"]),
                page_id=page.id,
                raw_jp_text=b["raw_jp_text"],
                bounding_box=b["bounding_box"],
                confidence=b["confidence"],
                reading_order_index=b["reading_order_index"],
                is_sfx=b["is_sfx"],
                bubble_shape=b["bubble_shape"],
                contour_points=b["contour_points"],
                usable_area_polygon=b["usable_area_polygon"],
                bg_color_hex=b["bg_color_hex"],
                suggested_font=b["suggested_font"],
            )
            session.add(ocr_block)
        session.commit()

    task_translate_page.apply_async(args=[page_id], queue="translate")
    return {"page_id": page_id, "blocks": len(blocks)}


# ── Task 3: Translate all blocks on a page ──────────────────────────────────

@celery_app.task(bind=True, max_retries=2, queue="translate", name="tasks.translate_page")
def task_translate_page(self, page_id: str):
    log.info("Translating page", page_id=page_id)
    with Session(sync_engine) as session:
        page = session.get(MangaPage, uuid.UUID(page_id))
        if not page:
            return

        _set_page_status(session, page_id, ProcessingStatus.translating)

        # Build context from prior pages in same chapter
        prior = session.execute(
            select(OCRBlock)
            .join(MangaPage)
            .where(
                MangaPage.chapter_id == page.chapter_id,
                MangaPage.page_number < page.page_number,
                MangaPage.page_number >= page.page_number - settings.context_window_pages,
            )
            .order_by(MangaPage.page_number, OCRBlock.reading_order_index)
        ).scalars().all()

        context_data = [{"page_number": b.page.page_number, "raw_jp_text": b.raw_jp_text} for b in prior]
        context_text = build_context_text(context_data)

        # Fetch glossary for this chapter
        glossary = session.execute(
            select(GlossaryTerm).where(GlossaryTerm.chapter_id == page.chapter_id)
        ).scalars().all()
        glossary_dicts = [{"japanese_term": g.japanese_term, "english_term": g.english_term, "term_type": g.term_type} for g in glossary]

        # Translate each block
        blocks = session.execute(
            select(OCRBlock)
            .where(OCRBlock.page_id == page.id)
            .order_by(OCRBlock.reading_order_index)
        ).scalars().all()

        for block in blocks:
            try:
                result = translate_block(
                    jp_text=block.raw_jp_text,
                    bubble_shape=block.bubble_shape or "smooth_oval",
                    context_text=context_text,
                    glossary=glossary_dicts,
                )
                font_name, font_size = select_font_for_block(
                    block.bubble_shape or "smooth_oval",
                    result.get("tone_label", "dialogue"),
                    block.is_sfx,
                )
                block.final_english_text = result.get("english_text", "")
                block.tone_label = result.get("tone_label", "dialogue")
                block.tl_note = result.get("tl_note")
                block.font_family = font_name
                block.font_size_pt = font_size
            except Exception as e:
                log.error("Translation failed for block", block_id=str(block.id), error=str(e))
                block.final_english_text = block.raw_jp_text  # preserve original on failure

        session.commit()

    task_typeset_page.apply_async(args=[page_id], queue="typeset")
    return {"page_id": page_id}


# ── Task 4: Inpaint + typeset ───────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=2, queue="typeset", name="tasks.typeset_page")
def task_typeset_page(self, page_id: str):
    log.info("Typesetting page", page_id=page_id)
    with Session(sync_engine) as session:
        page = session.get(MangaPage, uuid.UUID(page_id))
        if not page:
            return

        _set_page_status(session, page_id, ProcessingStatus.inpainting)

        raw_bytes = storage.download_image_bytes(page.raw_image_s3_key)
        blocks = session.execute(
            select(OCRBlock).where(OCRBlock.page_id == page.id)
        ).scalars().all()
        block_dicts = [
            {
                "bounding_box": b.bounding_box,
                "usable_area_polygon": b.usable_area_polygon,
                "final_english_text": b.final_english_text,
                "font_family": b.font_family,
                "font_size_pt": b.font_size_pt,
                "suggested_font": b.suggested_font,
                "is_dark_bg": False,
            }
            for b in blocks
        ]

        try:
            inpainted_bytes = inpaint_text_regions(raw_bytes, block_dicts)
            inpainted_key = storage.upload_image_bytes(inpainted_bytes, prefix="inpainted")
            page.inpainted_s3_key = inpainted_key
            session.commit()
        except Exception as exc:
            _set_page_status(session, page_id, ProcessingStatus.failed, str(exc))
            raise self.retry(exc=exc, countdown=30)

        _set_page_status(session, page_id, ProcessingStatus.typesetting)

        try:
            final_bytes = typeset_page(inpainted_bytes, block_dicts)
            final_key = storage.upload_image_bytes(final_bytes, prefix="final")
            page.final_s3_key = final_key
            page.status = ProcessingStatus.done
            session.commit()
        except Exception as exc:
            _set_page_status(session, page_id, ProcessingStatus.failed, str(exc))
            raise self.retry(exc=exc, countdown=30)

    return {"page_id": page_id, "final_key": final_key}
