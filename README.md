# Manga Omni-Translator

Professional-grade end-to-end pipeline for manga translation:
**Scrape → OCR → AI Localization → Inpaint → Typeset**

Matches the quality of the reference scanlation images — clean inpainted backgrounds, contour-fitted English text, tone-matched fonts.

---

## Architecture at a glance

```
Browser (Next.js :3000)
      │
      ▼
FastAPI API (:8000)  ←──  WebSocket live status
      │
      ▼
Celery workers  (Redis :6379 as broker)
  ├── scraper    →  Playwright / MangaDex API
  ├── ocr        →  manga-ocr + OpenCV bubble CV
  ├── translate  →  Claude claude-opus-4-5 (Anthropic)
  └── typeset    →  OpenCV inpaint + Shapely wrapping + PIL render
      │
      ├── PostgreSQL :5432  (page state + glossary)
      ├── Redis :6379        (queue + context cache)
      └── MinIO :9000        (S3-compatible image store)
```

---

## Prerequisites — install these first

| Tool | Min version | Install |
|------|-------------|---------|
| **Docker Desktop** | 24+ | https://www.docker.com/products/docker-desktop |
| **Docker Compose** | v2 | Bundled with Docker Desktop |
| **Node.js** | 18+ | https://nodejs.org |
| **Python** | 3.11+ | https://python.org (for running setup helper) |

You also need an **Anthropic API key** — get one free at https://console.anthropic.com.

> **GPU note:** Not required. The pipeline runs on CPU. An Nvidia GPU with CUDA will speed up manga-ocr inference significantly, but it works fine without one.

---

## Quick start (5 steps)

### Step 1 — Clone the project

```bash
git clone <your-repo-url> manga-omni-translator
cd manga-omni-translator
```

### Step 2 — Run the setup script

```bash
bash scripts/setup.sh
```

The first run will:
1. Create a `.env` file from `.env.example`
2. Tell you to add your API key — then stop

**Open `.env` and replace `sk-ant-YOUR_KEY_HERE` with your real Anthropic key.**

Then run the script again:

```bash
bash scripts/setup.sh
```

This time it will:
- Download the Bangers font automatically
- Build all Docker images (takes 5–10 min on first run — it downloads manga-ocr, OpenCV, Playwright)
- Start all services

### Step 3 — (Recommended) Add manga fonts

The pipeline uses these free freeware fonts for best output quality:

1. Go to **https://www.blambot.com/pages/lettering-fonts**
2. Download **Anime Ace 2.0 BB** → save the `.ttf` as `backend/app/fonts/AnimeAce2.ttf`
3. Download **Manga Temple** → save as `backend/app/fonts/MangaTemple.ttf`

Without these, PIL's default font is used (looks worse but still works).

### Step 4 — Open the app

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **API docs (Swagger)** | http://localhost:8000/docs |
| **Queue dashboard (Flower)** | http://localhost:5555 |
| **Image storage (MinIO)** | http://localhost:9001 (login: minioadmin / minioadmin) |

### Step 5 — Translate your first chapter

**Option A — MangaDex URL (easiest)**
1. Go to MangaDex, find a chapter, copy the URL (e.g. `https://mangadex.org/chapter/abc.../1`)
2. Paste it into the frontend "New Chapter" form
3. Watch the pipeline progress in real time

**Option B — Manual image upload (no scraper needed, great for testing)**
1. Submit any URL (or a dummy one) to create a chapter record
2. Open the chapter in the frontend
3. Click a page → use "Upload Image" to upload a `.jpg` or `.png` manga page directly
4. The OCR → Translate → Typeset pipeline runs automatically

---

## Development workflow (without Docker)

If you want to edit code and see changes without rebuilding containers:

### Backend (Python)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# You need Postgres, Redis, MinIO running separately (or keep docker-compose up for just those)
docker-compose up -d postgres redis minio

# Run API with auto-reload
uvicorn app.main:app --reload --port 8000

# In separate terminals, run workers:
celery -A app.workers.celery_app worker -Q scraper -c 2 --loglevel=info
celery -A app.workers.celery_app worker -Q ocr -c 1 --loglevel=info
celery -A app.workers.celery_app worker -Q translate,typeset -c 2 --loglevel=info
```

### Frontend (Node.js)

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000
```

---

## Upgrading to production-quality inpainting (LaMa)

The default inpainter uses OpenCV's `INPAINT_TELEA` which is fast but imperfect on complex screentone patterns.

To get the quality shown in the reference images, install **LaMa**:

```bash
pip install lama-cleaner
```

Then in `backend/app/services/typesetter.py`, replace the `inpaint_text_regions` function body with:

```python
from lama_cleaner.model import LaMa
from lama_cleaner.schema import Config

_lama = None
def get_lama():
    global _lama
    if _lama is None:
        _lama = LaMa(device="cuda" if torch.cuda.is_available() else "cpu")
    return _lama

def inpaint_text_regions(image_bytes: bytes, ocr_blocks: list[dict]) -> bytes:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    for block in ocr_blocks:
        bb = block["bounding_box"]
        cv2.rectangle(mask, (bb["x"]-5, bb["y"]-5),
                      (bb["x"]+bb["w"]+5, bb["y"]+bb["h"]+5), 255, cv2.FILLED)
    result = get_lama()(
        image=img_rgb,
        mask=mask,
        config=Config(hd_strategy="Resize", hd_strategy_resize_limit=2048),
    )
    _, buf = cv2.imencode(".jpg", cv2.cvtColor(result, cv2.COLOR_RGB2BGR),
                          [cv2.IMWRITE_JPEG_QUALITY, 95])
    return buf.tobytes()
```

---

## Environment variables reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Your Claude API key |
| `DATABASE_URL` | postgres://... | PostgreSQL connection string |
| `REDIS_URL` | redis://... | Redis URL |
| `S3_ENDPOINT` | http://minio:9000 | S3-compatible endpoint |
| `S3_ACCESS_KEY` | minioadmin | MinIO / S3 access key |
| `S3_SECRET_KEY` | minioadmin | MinIO / S3 secret key |
| `S3_BUCKET` | manga-pages | Bucket name |
| `CONTEXT_WINDOW_PAGES` | 5 | Pages of prior context fed to translator |
| `TRANSLATION_MODEL` | claude-opus-4-5 | Anthropic model to use |
| `MIN_OCR_CONFIDENCE` | 0.7 | Below this, fall back to secondary OCR |

---

## Project structure

```
manga-omni-translator/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI app + all routes
│   │   ├── core/
│   │   │   ├── config.py        ← Settings (pydantic-settings)
│   │   │   └── database.py      ← SQLAlchemy async engine
│   │   ├── models/
│   │   │   ├── db_models.py     ← ORM tables
│   │   │   └── schemas.py       ← Pydantic API schemas
│   │   ├── services/
│   │   │   ├── scraper.py       ← Playwright + MangaDex scrapers
│   │   │   ├── ocr.py           ← manga-ocr + bubble CV
│   │   │   ├── translation.py   ← Claude translation engine
│   │   │   ├── typesetter.py    ← Inpaint + shapely wrap + PIL render
│   │   │   └── storage.py       ← S3 / MinIO helpers
│   │   ├── workers/
│   │   │   └── celery_app.py    ← All Celery tasks
│   │   └── fonts/               ← Place TTF fonts here
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                    ← Dashboard / home
│   │   │   ├── chapters/[id]/page.tsx      ← Chapter viewer
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/StatusBadge.tsx
│   │   │   └── pipeline/
│   │   │       ├── SubmitForm.tsx
│   │   │       ├── ChapterList.tsx
│   │   │       ├── PageViewer.tsx           ← Image + OCR overlay + editor
│   │   │       └── GlossaryManager.tsx
│   │   ├── lib/api.ts           ← All API calls
│   │   └── types/index.ts       ← TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
├── scripts/
│   └── setup.sh                 ← One-command setup
├── docker-compose.yml
└── .env.example
```

---

## Troubleshooting

**"manga-ocr takes a long time on first use"**
— Normal. It downloads the model weights (~400 MB) on first inference. Subsequent runs are fast.

**"playwright: browser not found"**
— Run `playwright install chromium` inside the container:
`docker-compose exec api playwright install chromium --with-deps`

**"Translation returns the original Japanese"**
— Check `ANTHROPIC_API_KEY` is set correctly in `.env`. Check `docker-compose logs worker_translate`.

**"Images not showing in frontend"**
— MinIO presigned URLs are generated for `localhost:9000`. If you're on a remote server, set `S3_ENDPOINT` to your server's public IP/hostname.

**Resetting everything**
```bash
docker-compose down -v   # -v removes volumes (wipes DB + stored images)
docker-compose up -d
```
