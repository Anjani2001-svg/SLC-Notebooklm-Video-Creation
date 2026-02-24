# 🎬 NotebookLM Video Studio — Batch Mode

Upload multiple PDFs → Auto-generate video overviews via NotebookLM → Add intro/outro → Download all.

## Features

- **Batch Queue** — Upload 10+ PDFs, process all automatically
- **Password Protected** — Team-only access
- **Shared Google Account** — One NotebookLM login for the whole team
- **8 Visual Styles** — Classic, Whiteboard, Watercolor, Anime, etc.
- **Intro/Outro** — Set once, applied to all videos
- **Download All as ZIP** — Bulk export
- **Admin Panel** — Update auth when session expires (no re-deploy needed)
- **Cloud Ready** — Docker, Streamlit Cloud, Railway, VPS

---

## 🚀 Deployment Guide

### Option A: Streamlit Cloud (easiest, free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New App → select your repo
3. In **Advanced Settings → Secrets**, add:
   ```toml
   APP_PASSWORD = "your-team-password"
   ADMIN_PASSWORD = "your-admin-password"
   NOTEBOOKLM_AUTH_JSON = '{"cookies":[...],"origins":[]}'
   ```
4. `packages.txt` ensures FFmpeg is installed automatically

### Option B: Docker (VPS/AWS/GCP)

```bash
# 1. Copy .env.example to .env and fill in values
cp .env.example .env
nano .env

# 2. Build & run
docker-compose up -d

# 3. Access at http://your-server:8501
```

### Option C: Railway / Render

1. Connect GitHub repo
2. Set environment variables:
   - `APP_PASSWORD`
   - `ADMIN_PASSWORD`
   - `NOTEBOOKLM_AUTH_JSON`
   - `NOTEBOOKLM_HOME=/tmp/notebooklm`
3. Deploy

---

## 🔑 Getting NOTEBOOKLM_AUTH_JSON

This is the key step. You do this **on your local PC once**, then paste the result into your deployment:

```powershell
# 1. Install locally
pip install "notebooklm-py[browser]"
playwright install chromium

# 2. Set home directory
$env:NOTEBOOKLM_HOME = "C:\notebooklm"

# 3. Login (opens browser)
notebooklm login

# 4. Sign in, then CLOSE the browser

# 5. Verify
notebooklm list

# 6. Copy the auth file content
Get-Content "C:\notebooklm\storage_state.json"
```

Copy the entire JSON output and paste it as `NOTEBOOKLM_AUTH_JSON` in your deployment secrets.

---

## 🔄 When Auth Expires (~every 2 weeks)

**Option 1: Admin Panel (no re-deploy)**
1. Open the app → Sidebar → Admin → enter admin password
2. On your local PC: `notebooklm login` → close browser
3. Copy `C:\notebooklm\storage_state.json` content
4. Paste into the Admin panel → Update Auth

**Option 2: Update secrets**
1. Re-login locally as above
2. Update `NOTEBOOKLM_AUTH_JSON` in Streamlit Cloud Secrets / Docker .env
3. Restart the app

---

## Local Development

```bash
# Install
pip install -r requirements.txt
pip install "notebooklm-py[browser]"
playwright install chromium

# Login
notebooklm login

# Run
streamlit run app.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_PASSWORD` | Optional | Team login password (empty = no password) |
| `ADMIN_PASSWORD` | Optional | Password for admin panel |
| `NOTEBOOKLM_AUTH_JSON` | **Yes** (cloud) | Contents of `storage_state.json` |
| `NOTEBOOKLM_HOME` | Optional | Auth storage path (default: `/tmp/notebooklm`) |

## Tech Stack

- [notebooklm-py](https://github.com/teng-lin/notebooklm-py) — Unofficial NotebookLM API
- [Streamlit](https://streamlit.io) — Web UI
- [FFmpeg](https://ffmpeg.org) — Video processing

## ⚠️ Notes

- `notebooklm-py` uses **undocumented Google APIs** — may break if Google changes them
- Sessions expire every **1-2 weeks** — use the admin panel to refresh
- Video generation takes **3-10 minutes per PDF** on Google's servers
- Concurrent users share the same queue (no user isolation)
