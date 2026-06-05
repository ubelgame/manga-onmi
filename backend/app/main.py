"""
FastAPI application with:
- Chapter submission and listing
- Page state and presigned image URLs
- WebSocket for live job progress
- Translation override (human-in-the-loop correction)
- Glossary management
"""
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import asyncio
import json

from app.core.database import get_db, init_db
from app.core.config import get_settings
from app.models.db_models import Chapter, MangaPage, OCRBlock, GlossaryTerm, ProcessingStatus
from app.models.schemas import (
    ChapterSubmit, ChapterOut, MangaPageOut, OCRBlockOut,
    PresignedUrlOut, GlossaryTermOut, TranslationOverride,
)
from app.services import storage
from app.services.storage import ensure_bucket_exists

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    ensure_bucket_exists()
    yield


app = FastAPI(title="Manga Omni-Translator API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket connection manager ────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, page_id: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(page_id, []).append(ws)

    def disconnect(self, page_id: str, ws: WebSocket):
        self.connections.get(page_id, []).remove(ws)

    async def broadcast(self, page_id: str, data: dict):
        for ws in self.connections.get(page_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


# ── Chapter endpoints ───────────────────────────────────────────────────────

@app.post("/chapters", response_model=ChapterOut)
async def submit_chapter(body: ChapterSubmit, db: AsyncSession = Depends(get_db)):
    from app.workers.celery_app import task_scrape_chapter
    chapter = Chapter(
        source_url=body.source_url,
        series_name=body.series_name,
        chapter_number=body.chapter_number,
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    task_scrape_chapter.apply_async(args=[str(chapter.id)], queue="scraper")
    return ChapterOut(
        id=chapter.id,
        series_name=chapter.series_name,
        chapter_number=chapter.chapter_number,
        source_url=chapter.source_url,
        status=chapter.status,
        created_at=chapter.created_at,
        page_count=0,
    )


@app.get("/chapters", response_model=list[ChapterOut])
async def list_chapters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chapter).order_by(Chapter.created_at.desc()))
    chapters = result.scalars().all()
    out = []
    for c in chapters:
        count_result = await db.execute(
            select(func.count()).where(MangaPage.chapter_id == c.id)
        )
        count = count_result.scalar() or 0
        out.append(ChapterOut(
            id=c.id, series_name=c.series_name, chapter_number=c.chapter_number,
            source_url=c.source_url, status=c.status, created_at=c.created_at,
            page_count=count,
        ))
    return out


@app.get("/chapters/{chapter_id}/pages", response_model=list[MangaPageOut])
async def list_pages(chapter_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MangaPage)
        .where(MangaPage.chapter_id == chapter_id)
        .order_by(MangaPage.page_number)
    )
    pages = result.scalars().all()
    out = []
    for p in pages:
        blocks_result = await db.execute(
            select(OCRBlock).where(OCRBlock.page_id == p.id).order_by(OCRBlock.reading_order_index)
        )
        blocks = blocks_result.scalars().all()
        out.append(MangaPageOut(
            id=p.id, chapter_id=p.chapter_id, page_number=p.page_number,
            status=p.status, raw_image_s3_key=p.raw_image_s3_key,
            inpainted_s3_key=p.inpainted_s3_key, final_s3_key=p.final_s3_key,
            error_message=p.error_message,
            created_at=p.created_at, updated_at=p.updated_at,
            ocr_blocks=[OCRBlockOut.model_validate(b) for b in blocks],
        ))
    return out


# ── Page endpoints ──────────────────────────────────────────────────────────

@app.get("/pages/{page_id}", response_model=MangaPageOut)
async def get_page(page_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    page = await db.get(MangaPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    blocks_result = await db.execute(
        select(OCRBlock).where(OCRBlock.page_id == page_id).order_by(OCRBlock.reading_order_index)
    )
    blocks = blocks_result.scalars().all()
    return MangaPageOut(
        id=page.id, chapter_id=page.chapter_id, page_number=page.page_number,
        status=page.status, raw_image_s3_key=page.raw_image_s3_key,
        inpainted_s3_key=page.inpainted_s3_key, final_s3_key=page.final_s3_key,
        error_message=page.error_message,
        created_at=page.created_at, updated_at=page.updated_at,
        ocr_blocks=[OCRBlockOut.model_validate(b) for b in blocks],
    )


@app.get("/pages/{page_id}/image-url", response_model=PresignedUrlOut)
async def get_image_url(page_id: uuid.UUID, stage: str = "final", db: AsyncSession = Depends(get_db)):
    """Generate a presigned URL to view the page image at any pipeline stage."""
    page = await db.get(MangaPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    key_map = {
        "raw": page.raw_image_s3_key,
        "inpainted": page.inpainted_s3_key,
        "final": page.final_s3_key,
    }
    key = key_map.get(stage) or page.raw_image_s3_key
    if not key:
        raise HTTPException(status_code=404, detail="Image not yet available")
    url = storage.get_presigned_url(key)
    return PresignedUrlOut(url=url)


@app.post("/pages/{page_id}/reprocess")
async def reprocess_page(page_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.workers.celery_app import task_ocr_page
    page = await db.get(MangaPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    page.status = ProcessingStatus.queued
    await db.commit()
    task_ocr_page.apply_async(args=[str(page_id)], queue="ocr")
    return {"status": "requeued"}


@app.post("/pages/{page_id}/upload")
async def upload_page_image(page_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Allow manual upload of a page image (for testing without a scraper URL)."""
    from app.workers.celery_app import task_ocr_page
    contents = await file.read()
    key = storage.upload_image_bytes(contents, prefix="raw")
    page = await db.get(MangaPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    page.raw_image_s3_key = key
    page.status = ProcessingStatus.queued
    await db.commit()
    task_ocr_page.apply_async(args=[str(page_id)], queue="ocr")
    return {"s3_key": key, "status": "queued"}


# ── Translation override ────────────────────────────────────────────────────

@app.patch("/blocks/{block_id}/translation")
async def override_translation(
    block_id: uuid.UUID,
    body: TranslationOverride,
    db: AsyncSession = Depends(get_db),
):
    block = await db.get(OCRBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    block.final_english_text = body.english_text
    block.tl_note = body.tl_note
    await db.commit()
    return {"status": "updated"}


# ── Glossary ────────────────────────────────────────────────────────────────

@app.get("/chapters/{chapter_id}/glossary", response_model=list[GlossaryTermOut])
async def get_glossary(chapter_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GlossaryTerm).where(GlossaryTerm.chapter_id == chapter_id))
    return result.scalars().all()


@app.post("/chapters/{chapter_id}/glossary", response_model=GlossaryTermOut)
async def add_glossary_term(
    chapter_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    term = GlossaryTerm(
        chapter_id=chapter_id,
        japanese_term=body["japanese_term"],
        english_term=body["english_term"],
        term_type=body.get("term_type", "general"),
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


# ── WebSocket for live status updates ───────────────────────────────────────

@app.websocket("/ws/pages/{page_id}")
async def ws_page_status(page_id: str, websocket: WebSocket, db: AsyncSession = Depends(get_db)):
    await manager.connect(page_id, websocket)
    try:
        while True:
            page = await db.get(MangaPage, uuid.UUID(page_id))
            if page:
                await websocket.send_json({
                    "page_id": page_id,
                    "status": page.status.value,
                    "has_final": bool(page.final_s3_key),
                })
                if page.status in (ProcessingStatus.done, ProcessingStatus.failed):
                    break
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(page_id, websocket)


@app.get("/health")
async def health():
    return {"status": "ok"}
