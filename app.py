import streamlit as st
import subprocess
import os
import tempfile
import shutil
import json
import time
from pathlib import Path
from datetime import datetime

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NotebookLM Video Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; max-width: 1200px; }
    
    
    .app-header {
        background: linear-gradient(135deg, #0f9b8e 0%, #1a56db 100%);
        padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 2rem; color: white;
    }
    .app-header h1 { color: white !important; font-size: 2rem !important; margin-bottom: 0.3rem !important; }
    .app-header p { color: rgba(255,255,255,0.85); font-size: 1.05rem; margin: 0; }
    
    .step-card {
        background: #f8f9fb; border: 1px solid #e2e6ed;
        border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;
    }
    .step-card.active { border-color: #0f9b8e; background: #f0fdf9; }
    
    .step-badge {
        display: inline-flex; align-items: center; justify-content: center;
        width: 32px; height: 32px; border-radius: 50%;
        background: #0f9b8e; color: white; font-weight: 700;
        font-size: 0.9rem; margin-right: 0.75rem;
    }
    
    .info-box {
        background: #eff6ff; border-left: 4px solid #3b82f6;
        padding: 1rem 1.25rem; border-radius: 0 8px 8px 0;
        margin: 1rem 0; font-size: 0.95rem;
    }
    .success-box {
        background: #f0fdf4; border-left: 4px solid #22c55e;
        padding: 1rem 1.25rem; border-radius: 0 8px 8px 0;
        margin: 1rem 0; font-size: 0.95rem;
    }
    
    .status-connected { color: #22c55e; font-weight: 600; }
    .status-disconnected { color: #ef4444; font-weight: 600; }
    
    .stDownloadButton > button {
        background: linear-gradient(135deg, #0f9b8e 0%, #1a56db 100%) !important;
        color: white !important; border: none !important;
        padding: 0.75rem 2rem !important; font-size: 1.1rem !important;
        border-radius: 10px !important; width: 100%;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ─── NotebookLM Integration Functions ────────────────────────────────────────

def run_notebooklm_cmd(args, timeout=300):
    """Run a notebooklm CLI command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["notebooklm"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return False, "", "notebooklm-py is not installed. Run: pip install 'notebooklm-py[browser]'"
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def check_notebooklm_installed():
    """Check if notebooklm-py CLI is available."""
    success, _, _ = run_notebooklm_cmd(["--version"], timeout=10)
    return success


def check_notebooklm_auth():
    """Check if user is authenticated by trying to list notebooks."""
    success, stdout, _ = run_notebooklm_cmd(["list"], timeout=30)
    return success


def notebooklm_login():
    """Trigger browser-based login."""
    success, stdout, stderr = run_notebooklm_cmd(["login"], timeout=120)
    if success:
        return True, "Successfully logged in to NotebookLM!"
    return False, f"Login failed: {stderr or 'Please try again'}"


def create_notebook(title):
    """Create a new notebook. Returns (success, notebook_id, message)."""
    success, stdout, stderr = run_notebooklm_cmd(["create", title], timeout=60)
    if success:
        for line in stdout.split("\n"):
            if "notebook" in line.lower() and ("id" in line.lower() or "/" in line):
                parts = line.strip().split()
                for part in parts:
                    if len(part) > 10 and not part.startswith("http"):
                        return True, part.strip(), stdout
        return True, stdout.strip(), "Notebook created"
    return False, "", f"Failed to create notebook: {stderr}"


def add_pdf_source(notebook_id, pdf_path):
    """Add a PDF file as a source to the notebook."""
    run_notebooklm_cmd(["use", notebook_id], timeout=30)
    success, stdout, stderr = run_notebooklm_cmd(
        ["source", "add", pdf_path], timeout=120
    )
    if success:
        return True, f"PDF added successfully"
    return False, f"Failed to add PDF: {stderr}"


def generate_video(notebook_id, style="classic", prompt=None):
    """Generate a video overview."""
    run_notebooklm_cmd(["use", notebook_id], timeout=30)
    cmd = ["generate", "video", "--wait"]
    if style and style != "auto":
        cmd.extend(["--style", style])
    if prompt:
        cmd.append(prompt)
    success, stdout, stderr = run_notebooklm_cmd(cmd, timeout=600)
    if success:
        return True, f"Video generated successfully"
    return False, f"Video generation failed: {stderr}"


def download_video(notebook_id, output_path):
    """Download the generated video."""
    run_notebooklm_cmd(["use", notebook_id], timeout=30)
    success, stdout, stderr = run_notebooklm_cmd(
        ["download", "video", output_path], timeout=300
    )
    if success and os.path.exists(output_path):
        return True, output_path, "Video downloaded"
    return False, "", f"Download failed: {stderr}"


# ─── Video Processing Functions ──────────────────────────────────────────────

def get_work_dir():
    if "work_dir" not in st.session_state:
        st.session_state.work_dir = tempfile.mkdtemp(prefix="nblm_video_")
    return st.session_state.work_dir


def save_uploaded_file(uploaded_file, filename):
    work_dir = get_work_dir()
    filepath = os.path.join(work_dir, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath


def get_video_info(filepath):
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        vs = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), {})
        audio = next((s for s in data.get("streams", []) if s["codec_type"] == "audio"), {})
        fps_str = vs.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            n, d = fps_str.split("/")
            fps = float(n) / float(d) if float(d) else 0
        else:
            fps = float(fps_str)
        return {
            "duration": duration,
            "duration_str": f"{int(duration // 60)}:{int(duration % 60):02d}",
            "width": int(vs.get("width", 0)), "height": int(vs.get("height", 0)),
            "fps": fps, "has_audio": bool(audio),
            "size_mb": os.path.getsize(filepath) / (1024 * 1024),
        }
    except Exception as e:
        return {"error": str(e), "duration": 0, "duration_str": "0:00",
                "width": 0, "height": 0, "fps": 0, "size_mb": 0, "has_audio": False}


def combine_videos(intro_path, main_path, outro_path, output_path,
                    target_resolution="1920x1080", target_fps=30,
                    progress_callback=None):
    parts, labels = [], []
    if intro_path and os.path.exists(intro_path):
        parts.append(intro_path); labels.append("intro")
    if main_path and os.path.exists(main_path):
        parts.append(main_path); labels.append("main")
    if outro_path and os.path.exists(outro_path):
        parts.append(outro_path); labels.append("outro")
    
    if not parts:
        return False, "No video files provided"
    if len(parts) == 1:
        shutil.copy2(parts[0], output_path)
        return True, "Single video copied"
    
    work_dir = get_work_dir()
    w, h = target_resolution.split("x")
    
    normalized_parts = []
    for i, (part, label) in enumerate(zip(parts, labels)):
        if progress_callback:
            progress_callback(f"Normalizing {label} video... ({i+1}/{len(parts)})")
        normalized = os.path.join(work_dir, f"normalized_{label}.mp4")
        info = get_video_info(part)
        
        if info.get("has_audio", False):
            cmd = [
                "ffmpeg", "-y", "-i", part,
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                       f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps={target_fps}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                normalized
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", part,
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                       f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps={target_fps}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest", normalized
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            return False, f"Error normalizing {label}: {result.stderr[-500:]}"
        normalized_parts.append(normalized)
    
    if progress_callback:
        progress_callback("Combining all parts...")
    
    concat_file = os.path.join(work_dir, "concat_list.txt")
    with open(concat_file, "w") as f:
        for part in normalized_parts:
            f.write(f"file '{part}'\n")
    
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path],
        capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        return False, f"Error concatenating: {result.stderr[-500:]}"
    
    if progress_callback:
        progress_callback("Done!")
    return True, "Videos combined successfully"


# ─── Session State Init ──────────────────────────────────────────────────────
defaults = {
    "intro_file": None, "main_file": None, "outro_file": None,
    "combined_file": None, "notebook_id": None, "pdf_path": None,
    "is_authenticated": None, "is_installed": None,
    "video_generated": False, "nlm_video_path": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>🎬 NotebookLM Video Studio</h1>
    <p>Upload PDF → Auto-generate Video Overview via NotebookLM → Add Intro & Outro → Download Final Video</p>
</div>
""", unsafe_allow_html=True)


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔌 Connection Status")
    
    if st.session_state.is_installed is None:
        st.session_state.is_installed = check_notebooklm_installed()
    
    if st.session_state.is_installed:
        st.markdown("✅ `notebooklm-py` installed")
        
        if st.session_state.is_authenticated is None:
            st.session_state.is_authenticated = check_notebooklm_auth()
        
        if st.session_state.is_authenticated:
            st.markdown('<span class="status-connected">🟢 Connected to NotebookLM</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-disconnected">🔴 Not logged in</span>',
                        unsafe_allow_html=True)
            if st.button("🔑 Login to NotebookLM", use_container_width=True):
                with st.spinner("Opening browser for Google login..."):
                    success, msg = notebooklm_login()
                if success:
                    st.session_state.is_authenticated = True
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.markdown('<span class="status-disconnected">❌ notebooklm-py not found</span>',
                    unsafe_allow_html=True)
        st.code(
            'pip install "notebooklm-py[browser]"\n'
            'playwright install chromium\n'
            'notebooklm login',
            language="bash"
        )
        if st.button("🔄 Re-check", use_container_width=True):
            st.session_state.is_installed = None
            st.session_state.is_authenticated = None
            st.rerun()
    
    st.divider()
    st.markdown("### ⚙️ Output Settings")
    
    resolution = st.selectbox(
        "Resolution",
        ["1920x1080 (Full HD)", "1280x720 (HD)", "3840x2160 (4K)"],
        index=0,
    )
    target_res = resolution.split(" ")[0]
    target_fps = st.selectbox("FPS", [24, 30, 60], index=1)
    
    st.divider()
    st.markdown("### 🎨 NotebookLM Style")
    video_style = st.selectbox(
        "Visual Style",
        ["classic", "whiteboard", "watercolor", "retro-print",
         "heritage", "paper-craft", "kawaii", "anime", "auto"],
        index=0,
    )
    
    st.divider()
    if st.button("🗑️ Reset All", use_container_width=True):
        wd = get_work_dir() if "work_dir" in st.session_state else None
        if wd and os.path.exists(wd):
            shutil.rmtree(wd, ignore_errors=True)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# STEP 1: Upload PDF & Create Notebook
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;">'
            '<span class="step-badge">1</span>'
            '<h3 style="margin:0;">Upload PDF & Create NotebookLM Notebook</h3></div>',
            unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    pdf_file = st.file_uploader("Upload PDF document", type=["pdf"], key="pdf_uploader")
    
    if pdf_file:
        pdf_path = save_uploaded_file(pdf_file, f"source_{pdf_file.name}")
        st.session_state.pdf_path = pdf_path
        st.success(f"✅ **{pdf_file.name}** ({pdf_file.size / 1024:.0f} KB)")
        
        notebook_title = st.text_input(
            "Notebook Title",
            value=pdf_file.name.replace(".pdf", "").replace("_", " ").title(),
        )
        
        if st.session_state.is_authenticated:
            if st.session_state.notebook_id is None:
                if st.button("📚 Create Notebook & Upload PDF", use_container_width=True, type="primary"):
                    with st.spinner("Creating notebook..."):
                        success, nb_id, msg = create_notebook(notebook_title)
                    if success:
                        st.session_state.notebook_id = nb_id
                        with st.spinner("Uploading PDF to NotebookLM..."):
                            src_ok, src_msg = add_pdf_source(nb_id, pdf_path)
                        if src_ok:
                            st.success("✅ Notebook created & PDF uploaded!")
                            st.rerun()
                        else:
                            st.error(src_msg)
                    else:
                        st.error(msg)
            else:
                st.markdown(f'<div class="success-box">✅ Notebook ready — ID: '
                            f'<code>{st.session_state.notebook_id}</code></div>',
                            unsafe_allow_html=True)
        elif not st.session_state.is_installed:
            st.warning("⚠️ Install notebooklm-py first (see sidebar)")
        else:
            st.warning("⚠️ Login to NotebookLM first (see sidebar)")

with col2:
    st.markdown("""
    <div class="info-box">
        📄 <strong>Automated flow:</strong><br><br>
        1. PDF uploaded locally<br>
        2. Notebook created in NotebookLM<br>
        3. PDF added as source<br>
        4. Ready for video generation
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# STEP 2: Generate Video Overview
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;">'
            '<span class="step-badge">2</span>'
            '<h3 style="margin:0;">Generate Video Overview</h3></div>',
            unsafe_allow_html=True)

if st.session_state.notebook_id:
    steering_prompt = st.text_area(
        "Steering Prompt (guide what NotebookLM focuses on)",
        value="Create a comprehensive video overview covering all major topics and key concepts. "
              "Use clear, engaging explanations. Include visual elements like timelines and diagrams. "
              "End with key takeaways.",
        height=100,
    )
    
    st.caption(f"🎨 Style: **{video_style}** | ⏱️ Generation takes ~3-10 minutes")
    
    if not st.session_state.video_generated:
        if st.button("🎬 Generate Video Overview", use_container_width=True, type="primary"):
            progress = st.progress(0, text="Starting...")
            status = st.empty()
            
            status.info("⏳ Generating video in NotebookLM... This may take several minutes.")
            progress.progress(20, text="Generating...")
            
            prompt = steering_prompt.strip() or None
            style = video_style if video_style != "auto" else None
            ok, msg = generate_video(st.session_state.notebook_id, style=style, prompt=prompt)
            
            if ok:
                progress.progress(70, text="Downloading video...")
                work_dir = get_work_dir()
                video_out = os.path.join(work_dir, "notebooklm_overview.mp4")
                dl_ok, dl_path, dl_msg = download_video(st.session_state.notebook_id, video_out)
                
                if dl_ok:
                    progress.progress(100, text="Done!")
                    st.session_state.nlm_video_path = dl_path
                    st.session_state.main_file = dl_path
                    st.session_state.video_generated = True
                    st.rerun()
                else:
                    progress.progress(100)
                    status.error(f"❌ Download failed: {dl_msg}")
            else:
                progress.progress(100)
                status.error(f"❌ {msg}")
    else:
        st.markdown('<div class="success-box">✅ Video overview generated!</div>',
                    unsafe_allow_html=True)
        if st.session_state.nlm_video_path and os.path.exists(st.session_state.nlm_video_path):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.video(st.session_state.nlm_video_path)
            with c2:
                info = get_video_info(st.session_state.nlm_video_path)
                st.metric("Duration", info.get("duration_str", "?"))
                st.metric("Resolution", f"{info.get('width', '?')}×{info.get('height', '?')}")
                st.metric("Size", f"{info.get('size_mb', 0):.1f} MB")
        
        if st.button("🔄 Regenerate Video"):
            st.session_state.video_generated = False
            st.session_state.nlm_video_path = None
            st.session_state.main_file = None
            st.rerun()

else:
    st.markdown('<div class="step-card"><p style="text-align:center;color:#9ca3af;padding:1.5rem 0;">'
                '⬆️ Complete Step 1 first</p></div>', unsafe_allow_html=True)
    
    with st.expander("📂 Or upload a NotebookLM video manually"):
        manual = st.file_uploader("Upload video", type=["mp4", "mov", "avi", "mkv", "webm"],
                                  key="manual_vid")
        if manual:
            path = save_uploaded_file(manual, f"main_{manual.name}")
            st.session_state.main_file = path
            st.session_state.video_generated = True
            st.session_state.nlm_video_path = path
            st.success(f"✅ {manual.name} uploaded")


# ═══════════════════════════════════════════════════════════════════════
# STEP 3: Upload Intro & Outro
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;">'
            '<span class="step-badge">3</span>'
            '<h3 style="margin:0;">Add Intro & Outro Videos</h3></div>',
            unsafe_allow_html=True)

ci, co = st.columns(2)

with ci:
    st.markdown("#### 🎬 Intro Video")
    st.caption("Optional — plays before the overview")
    intro_file = st.file_uploader("intro", type=["mp4","mov","avi","mkv","webm"],
                                  key="intro_up", label_visibility="collapsed")
    if intro_file:
        intro_path = save_uploaded_file(intro_file, f"intro_{intro_file.name}")
        st.session_state.intro_file = intro_path
        st.video(intro_file)
        info = get_video_info(intro_path)
        st.caption(f"{info['duration_str']} | {info['width']}×{info['height']} | {info['size_mb']:.1f} MB")

with co:
    st.markdown("#### 🎬 Outro Video")
    st.caption("Optional — plays after the overview")
    outro_file = st.file_uploader("outro", type=["mp4","mov","avi","mkv","webm"],
                                  key="outro_up", label_visibility="collapsed")
    if outro_file:
        outro_path = save_uploaded_file(outro_file, f"outro_{outro_file.name}")
        st.session_state.outro_file = outro_path
        st.video(outro_file)
        info = get_video_info(outro_path)
        st.caption(f"{info['duration_str']} | {info['width']}×{info['height']} | {info['size_mb']:.1f} MB")


# ═══════════════════════════════════════════════════════════════════════
# STEP 4: Combine & Download
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;">'
            '<span class="step-badge">4</span>'
            '<h3 style="margin:0;">Combine & Download Final Video</h3></div>',
            unsafe_allow_html=True)

has_intro = st.session_state.get("intro_file") is not None
has_main = st.session_state.get("main_file") is not None
has_outro = st.session_state.get("outro_file") is not None

if has_main:
    parts_info = []
    total_dur = 0
    
    if has_intro:
        info = get_video_info(st.session_state.intro_file)
        total_dur += info["duration"]
        parts_info.append(f"🎬 Intro ({info['duration_str']})")
    
    info = get_video_info(st.session_state.main_file)
    total_dur += info["duration"]
    parts_info.append(f"📺 Overview ({info['duration_str']})")
    
    if has_outro:
        info = get_video_info(st.session_state.outro_file)
        total_dur += info["duration"]
        parts_info.append(f"🎬 Outro ({info['duration_str']})")
    
    total_str = f"{int(total_dur // 60)}:{int(total_dur % 60):02d}"
    
    st.markdown(f'<div class="step-card active"><strong>📎 Timeline:</strong>&nbsp;&nbsp;'
                f'{"&nbsp;→&nbsp;".join(parts_info)}'
                f'&nbsp;&nbsp;|&nbsp;&nbsp;<strong>Total: {total_str}</strong></div>',
                unsafe_allow_html=True)
    
    output_name = st.text_input("Filename", value=f"Final_Video_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    if has_intro or has_outro:
        if st.button("🚀 Combine Videos", use_container_width=True, type="primary"):
            work_dir = get_work_dir()
            output_path = os.path.join(work_dir, f"{output_name}.mp4")
            status = st.empty()
            bar = st.progress(0)
            
            def update(msg):
                status.info(f"⏳ {msg}")
            
            bar.progress(10)
            ok, msg = combine_videos(
                st.session_state.get("intro_file"),
                st.session_state.get("main_file"),
                st.session_state.get("outro_file"),
                output_path, target_res, target_fps, update
            )
            bar.progress(100)
            
            if ok and os.path.exists(output_path):
                st.session_state.combined_file = output_path
                status.success(f"✅ {msg}")
                st.rerun()
            else:
                status.error(f"❌ {msg}")
    else:
        st.session_state.combined_file = st.session_state.main_file
    
    final = st.session_state.get("combined_file")
    if final and os.path.exists(final):
        st.markdown("---")
        st.markdown("### ✅ Final Video Ready!")
        
        fi = get_video_info(final)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Duration", fi["duration_str"])
        c2.metric("Resolution", f"{fi['width']}×{fi['height']}")
        c3.metric("Size", f"{fi['size_mb']:.1f} MB")
        c4.metric("FPS", f"{fi['fps']:.0f}")
        
        st.video(final)
        
        with open(final, "rb") as f:
            st.download_button(
                f"⬇️ Download Final Video ({fi['size_mb']:.1f} MB)",
                f.read(), f"{output_name}.mp4", "video/mp4",
                use_container_width=True,
            )
else:
    st.markdown('<div class="step-card"><p style="text-align:center;color:#9ca3af;padding:2rem 0;">'
                '⬆️ Generate or upload a video overview first (Steps 1-2)</p></div>',
                unsafe_allow_html=True)


# ─── Footer ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown('<div style="text-align:center;padding:1rem;color:#9ca3af;font-size:0.85rem;">'
            '🎬 NotebookLM Video Studio &bull; '
            '<a href="https://github.com/teng-lin/notebooklm-py">notebooklm-py</a>'
            ' + Streamlit + FFmpeg</div>', unsafe_allow_html=True)
