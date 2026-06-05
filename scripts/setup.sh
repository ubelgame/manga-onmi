#!/usr/bin/env bash
# setup.sh — run this once after cloning to get everything ready
set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║      MANGA OMNI-TRANSLATOR — Setup           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. Check required tools
for cmd in docker docker-compose python3 node npm; do
  if ! command -v $cmd &>/dev/null; then
    echo "✗ '$cmd' not found. Please install it first."
    exit 1
  fi
done
echo "✓ Required tools found (docker, python3, node, npm)"

# 2. Create .env if missing
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠  Created .env from .env.example"
  echo "   → Open .env and add your ANTHROPIC_API_KEY before continuing."
  echo "   → Then run this script again."
  echo ""
  exit 0
fi

# Check key is set
if grep -q "YOUR_KEY_HERE" .env; then
  echo ""
  echo "⚠  You haven't set ANTHROPIC_API_KEY in .env yet."
  echo "   Get your key at: https://console.anthropic.com"
  echo "   Then rerun: bash scripts/setup.sh"
  echo ""
  exit 1
fi

echo "✓ .env found with API key set"

# 3. Create font directory and download free manga-compatible fonts
mkdir -p backend/app/fonts
echo ""
echo "Downloading fonts (Bangers, Anime Ace placeholder)…"

# Bangers (Google Fonts — OFL licensed)
BANGERS_URL="https://fonts.gstatic.com/s/bangers/v24/FeVQS0BTqb0h60ACL5la2bxii28wYQ.woff2"
# We download a TTF via a different URL; use a Python one-liner for cross-platform
python3 - <<'PYEOF'
import urllib.request, os

fonts = {
    "Bangers-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/bangers/Bangers-Regular.ttf",
}
font_dir = "backend/app/fonts"
for fname, url in fonts.items():
    dest = os.path.join(font_dir, fname)
    if not os.path.exists(dest):
        try:
            print(f"  Downloading {fname}…")
            urllib.request.urlretrieve(url, dest)
            print(f"  ✓ {fname}")
        except Exception as e:
            print(f"  ✗ Could not download {fname}: {e}")
            print(f"    Place any TTF font as '{dest}' manually.")
    else:
        print(f"  ✓ {fname} already present")
PYEOF

# Note: AnimeAce2 and MangaTemple are freeware fonts.
# Download them from:
#   AnimeAce2: https://www.blambot.com/products/anime-ace-2-0bb
#   MangaTemple: https://www.blambot.com/products/manga-temple
# Place TTFs as backend/app/fonts/AnimeAce2.ttf and backend/app/fonts/MangaTemple.ttf
cat <<'NOTE'

  ── FONT NOTE ────────────────────────────────────────────────────
  For the best quality output (matching the reference images),
  download these free freeware fonts from Blambot:
    • Anime Ace 2.0 BB → save as  backend/app/fonts/AnimeAce2.ttf
    • Manga Temple      → save as  backend/app/fonts/MangaTemple.ttf
  URL: https://www.blambot.com/pages/lettering-fonts
  ──────────────────────────────────────────────────────────────────

NOTE

# 4. Build and start Docker containers
echo ""
echo "Building Docker images (first run takes 5-10 min — downloading ML models)…"
docker-compose build

echo ""
echo "Starting all services…"
docker-compose up -d

# 5. Wait for API to be ready
echo ""
echo "Waiting for API to be ready…"
for i in {1..30}; do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ API is up at http://localhost:8000"
    break
  fi
  sleep 3
  echo "  … waiting ($i/30)"
done

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  All services running!                       ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Frontend   → http://localhost:3000          ║"
echo "║  API docs   → http://localhost:8000/docs     ║"
echo "║  Queue UI   → http://localhost:5555          ║"
echo "║  MinIO UI   → http://localhost:9001          ║"
echo "║             (user: minioadmin / minioadmin)  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "To stop:  docker-compose down"
echo "To logs:  docker-compose logs -f api worker_ocr worker_translate"
echo ""
