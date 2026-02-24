# 🎬 NotebookLM Video Studio

A Streamlit web tool that **directly connects to your NotebookLM account** to automatically generate video overviews from PDFs, then add custom intro/outro clips for a polished final video.

## Workflow

```
📄 Upload PDF → 🤖 Auto-generate in NotebookLM → 🎬 Add Intro/Outro → ⬇️ Download Final Video
```

## Features

- **Direct NotebookLM Integration** — Connects to your Google NotebookLM account via [`notebooklm-py`](https://github.com/teng-lin/notebooklm-py)
- **One-Click Video Generation** — Upload PDF, set a steering prompt, choose visual style, and generate
- **8 Visual Styles** — Classic, Whiteboard, Watercolor, Retro Print, Heritage, Paper-craft, Kawaii, Anime
- **Intro/Outro Support** — Upload your branded clips and auto-combine with the overview
- **Smart Video Combining** — FFmpeg handles mismatched resolutions, codecs, and frame rates
- **Configurable Output** — Resolution (720p/1080p/4K), frame rate, quality
- **Manual Fallback** — Can also manually upload a NotebookLM video if you prefer

## Prerequisites

- **Python 3.10+**
- **FFmpeg** installed and in PATH
- **Google Account** with NotebookLM access

## Quick Setup

### 1. Install FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Login to NotebookLM (one-time)

```bash
notebooklm login
```

This opens a browser window for Google authentication. Your session stays active for 1-2 weeks.

### 4. Run the App

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

## Usage

### Step 1: Upload PDF
Upload your PDF and click **"Create Notebook & Upload PDF"** — this automatically creates a notebook in NotebookLM and adds your PDF as a source.

### Step 2: Generate Video
Write a steering prompt (or use the default), pick a visual style, and click **"Generate Video Overview"**. The app sends the request to NotebookLM and downloads the result automatically.

### Step 3: Add Intro & Outro (Optional)
Upload your branded intro and outro video clips.

### Step 4: Combine & Download
Review the timeline, click **"Combine Videos"**, and download your final polished video.

## Sidebar Settings

| Setting | Options | Default |
|---------|---------|---------|
| Resolution | 720p, 1080p, 4K | 1080p |
| FPS | 24, 30, 60 | 30 |
| Visual Style | classic, whiteboard, watercolor, retro-print, heritage, paper-craft, kawaii, anime, auto | classic |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `notebooklm-py not found` | Run `pip install "notebooklm-py[browser]"` then `playwright install chromium` |
| `Not logged in` | Run `notebooklm login` in terminal, or click the Login button in the sidebar |
| Session expired | Re-run `notebooklm login` (sessions last ~1-2 weeks) |
| FFmpeg not found | Install FFmpeg and ensure it's in your system PATH |
| Video generation timeout | NotebookLM may be slow; try again or use a shorter PDF |

## Tech Stack

- [notebooklm-py](https://github.com/teng-lin/notebooklm-py) — Unofficial Python API for Google NotebookLM
- [Streamlit](https://streamlit.io/) — Web UI framework
- [FFmpeg](https://ffmpeg.org/) — Video processing

## ⚠️ Note

`notebooklm-py` uses **undocumented Google APIs** that can change without notice. It is not affiliated with Google. Best for personal/research use.

## License

MIT
