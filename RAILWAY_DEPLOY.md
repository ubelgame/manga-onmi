# Deploying to Railway — Step-by-Step

Railway can't auto-deploy a monorepo from the root.
You need to add each service individually with the correct Root Directory.
Follow these steps exactly.

---

## Step 1 — Push to GitHub

If you haven't already:
```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/manga-omni.git
git push -u origin main
```

---

## Step 2 — Delete the failed service on Railway

In your Railway project, click the failed `manga-onmi` service → Settings → scroll to bottom → **Delete Service**.

---

## Step 3 — Add PostgreSQL plugin

In your Railway project canvas:
- Click **+ New** → **Database** → **Add PostgreSQL**
- Railway creates a managed Postgres instance. Note the `DATABASE_URL` it provides — you'll see it in the plugin's Variables tab.

---

## Step 4 — Add Redis plugin

- Click **+ New** → **Database** → **Add Redis**
- Railway creates a managed Redis. Note the `REDIS_URL`.

---

## Step 5 — Add the API service

1. Click **+ New** → **GitHub Repo** → select your repo
2. Before deploying, click **Configure** (or it may ask immediately):
   - **Root Directory**: `backend`
   - **Builder**: Dockerfile
   - **Dockerfile Path**: `Dockerfile`
3. Go to the service's **Variables** tab and add:

| Variable | Value |
|----------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-YOUR_KEY` |
| `DATABASE_URL` | (copy from PostgreSQL plugin → Variables → `DATABASE_URL`) |
| `REDIS_URL` | (copy from Redis plugin → Variables → `REDIS_URL`) |
| `CELERY_BROKER_URL` | same as `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | same as `REDIS_URL` |
| `S3_ENDPOINT` | your Cloudflare R2 endpoint (see Step 7) |
| `S3_ACCESS_KEY` | your R2 access key |
| `S3_SECRET_KEY` | your R2 secret key |
| `S3_BUCKET` | `manga-pages` |

4. Click **Deploy**. Wait for it to go green.
5. Go to **Settings** → **Networking** → **Generate Domain**. Copy the URL (e.g. `https://manga-api-xxxx.up.railway.app`).

---

## Step 6 — Add the Worker service

1. Click **+ New** → **GitHub Repo** → same repo
2. Configure:
   - **Root Directory**: `backend`
   - **Builder**: Dockerfile
   - **Dockerfile Path**: `Dockerfile.worker`
3. **Variables** tab — add the same variables as Step 5, PLUS:

| Variable | Value |
|----------|-------|
| `QUEUES` | `scraper,ocr,translate,typeset` |
| `CONCURRENCY` | `2` |

4. Click **Deploy**.

---

## Step 7 — Set up Cloudflare R2 (free image storage)

Railway doesn't include object storage. Cloudflare R2 is free for 10GB/month.

1. Go to **cloudflare.com** → sign up free → left sidebar → **R2**
2. Click **Create bucket** → name it `manga-pages`
3. Go to **R2 Overview** → **Manage R2 API Tokens** → **Create API Token**
   - Permissions: Object Read & Write
   - Specify bucket: `manga-pages`
4. Copy:
   - **Access Key ID** → `S3_ACCESS_KEY`
   - **Secret Access Key** → `S3_SECRET_KEY`
   - **Endpoint URL** (shown on the token page, looks like `https://ACCOUNT_ID.r2.cloudflarestorage.com`) → `S3_ENDPOINT`
5. Add these to BOTH the `api` and `worker` services on Railway.

---

## Step 8 — Add the Frontend service

1. Click **+ New** → **GitHub Repo** → same repo
2. Configure:
   - **Root Directory**: `frontend`
   - **Builder**: Dockerfile (or Nixpacks — both work)
3. **Variables** tab:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | the API URL from Step 5 (e.g. `https://manga-api-xxxx.up.railway.app`) |

4. Click **Deploy**.
5. Go to **Settings** → **Networking** → **Generate Domain**.
   - This is your public website URL! 🎉

---

## Step 9 — Verify everything works

1. Open your frontend URL in the browser
2. Go to **http://YOUR_API_URL/health** — should return `{"status":"ok"}`
3. Go to **http://YOUR_API_URL/docs** — FastAPI Swagger UI

If anything is red, click **View Logs** on the failing service on Railway.

---

## Common errors

**"manga_ocr takes 2+ minutes on first deploy"**
→ Normal. It downloads the model (~400MB) on first startup. Railway's health check may
  restart it — set the health check timeout to 300s in Settings → Deploy.

**"DATABASE_URL connection refused"**
→ Make sure DATABASE_URL is the one from the Railway PostgreSQL plugin, not the
  docker-compose default.

**"Images not loading"**
→ Check S3_ENDPOINT is the full Cloudflare R2 URL including `https://`.
  Check the bucket name matches S3_BUCKET exactly.

**"Translation not working"**
→ Verify ANTHROPIC_API_KEY is set on the worker service (not just api).
