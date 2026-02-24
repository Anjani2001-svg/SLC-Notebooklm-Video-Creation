import streamlit as st
import subprocess
import os
import re
import tempfile
import shutil
import json
import time
from pathlib import Path
from datetime import datetime

# ─── CRITICAL: Set NOTEBOOKLM_HOME before anything else ─────────────────────
NOTEBOOKLM_HOME = os.environ.get("NOTEBOOKLM_HOME", r"C:\notebooklm")
os.environ["NOTEBOOKLM_HOME"] = NOTEBOOKLM_HOME

st.set_page_config(page_title="NotebookLM Video Studio", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; max-width: 1200px; }
    .app-header { background: linear-gradient(135deg, #0f9b8e 0%, #1a56db 100%); padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 2rem; color: white; }
    .app-header h1 { color: white !important; font-size: 2rem !important; margin-bottom: 0.3rem !important; }
    .app-header p { color: rgba(255,255,255,0.85); font-size: 1.05rem; margin: 0; }
    .step-card { background: #f8f9fb; border: 1px solid #e2e6ed; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
    .step-card.active { border-color: #0f9b8e; background: #f0fdf9; }
    .step-badge { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 50%; background: #0f9b8e; color: white; font-weight: 700; font-size: 0.9rem; margin-right: 0.75rem; }
    .info-box { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 1rem 1.25rem; border-radius: 0 8px 8px 0; margin: 1rem 0; font-size: 0.95rem; }
    .success-box { background: #f0fdf4; border-left: 4px solid #22c55e; padding: 1rem 1.25rem; border-radius: 0 8px 8px 0; margin: 1rem 0; font-size: 0.95rem; }
    .status-connected { color: #22c55e; font-weight: 600; }
    .status-disconnected { color: #ef4444; font-weight: 600; }
    .stDownloadButton > button { background: linear-gradient(135deg, #0f9b8e 0%, #1a56db 100%) !important; color: white !important; border: none !important; padding: 0.75rem 2rem !important; font-size: 1.1rem !important; border-radius: 10px !important; width: 100%; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─── UUID pattern ────────────────────────────────────────────────────────────
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)

def run_nlm(args, timeout=300):
    env = os.environ.copy()
    env["NOTEBOOKLM_HOME"] = NOTEBOOKLM_HOME
    try:
        r = subprocess.run(["notebooklm"] + args, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return False, "", "notebooklm-py not installed"
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def check_installed():
    ok, _, _ = run_nlm(["--version"], timeout=15)
    return ok

def check_auth():
    ok, out, err = run_nlm(["list"], timeout=60)
    return ok and "Not logged in" not in err and "Not logged in" not in out

def create_notebook(title):
    ok, out, err = run_nlm(["create", title], timeout=60)
    combined = out + "\n" + err
    match = UUID_RE.search(combined)
    if match:
        return True, match.group(0), combined
    if ok:
        return False, "", f"Created but no ID found: {combined}"
    return False, "", f"Failed: {combined}"

def add_pdf_source(nb_id, pdf_path):
    run_nlm(["use", nb_id], timeout=30)
    ok, out, err = run_nlm(["source", "add", pdf_path], timeout=180)
    if ok:
        return True, "PDF added"
    return False, f"Failed: {out}\n{err}"

def generate_video(nb_id, style=None, prompt=None):
    run_nlm(["use", nb_id], timeout=30)
    cmd = ["generate", "video", "--wait"]
    if style and style != "auto":
        cmd.extend(["--style", style])
    if prompt:
        cmd.append(prompt)
    ok, out, err = run_nlm(cmd, timeout=600)
    if ok:
        return True, "Video generated"
    return False, f"Failed: {out}\n{err}"

def download_video(nb_id, output_path):
    run_nlm(["use", nb_id], timeout=30)
    ok, out, err = run_nlm(["download", "video", output_path], timeout=300)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True, output_path, "Downloaded"
    return False, "", f"Failed: {out}\n{err}"

def get_work_dir():
    if "work_dir" not in st.session_state:
        st.session_state.work_dir = tempfile.mkdtemp(prefix="nblm_video_")
    return st.session_state.work_dir

def save_uploaded_file(uf, fn):
    fp = os.path.join(get_work_dir(), fn)
    with open(fp, "wb") as f:
        f.write(uf.getbuffer())
    return fp

def get_video_info(filepath):
    try:
        r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format","-show_streams",filepath], capture_output=True, text=True, timeout=30)
        d = json.loads(r.stdout)
        dur = float(d.get("format",{}).get("duration",0))
        vs = next((s for s in d.get("streams",[]) if s["codec_type"]=="video"), {})
        au = next((s for s in d.get("streams",[]) if s["codec_type"]=="audio"), {})
        fs = vs.get("r_frame_rate","0/1")
        fps = float(fs.split("/")[0])/float(fs.split("/")[1]) if "/" in fs and float(fs.split("/")[1]) else float(fs) if fs else 0
        return {"duration":dur,"duration_str":f"{int(dur//60)}:{int(dur%60):02d}","width":int(vs.get("width",0)),"height":int(vs.get("height",0)),"fps":fps,"has_audio":bool(au),"size_mb":os.path.getsize(filepath)/(1024*1024)}
    except:
        return {"duration":0,"duration_str":"0:00","width":0,"height":0,"fps":0,"size_mb":0,"has_audio":False}

def combine_videos(intro, main, outro, output, res="1920x1080", fps=30, cb=None):
    parts, labels = [], []
    if intro and os.path.exists(intro): parts.append(intro); labels.append("intro")
    if main and os.path.exists(main): parts.append(main); labels.append("main")
    if outro and os.path.exists(outro): parts.append(outro); labels.append("outro")
    if not parts: return False, "No files"
    if len(parts) == 1: shutil.copy2(parts[0], output); return True, "Copied"
    wd = get_work_dir(); w, h = res.split("x")
    norms = []
    for i,(p,l) in enumerate(zip(parts,labels)):
        if cb: cb(f"Normalizing {l}... ({i+1}/{len(parts)})")
        n = os.path.join(wd, f"norm_{l}.mp4"); info = get_video_info(p)
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps={fps}"
        if info.get("has_audio"):
            cmd = ["ffmpeg","-y","-i",p,"-vf",vf,"-c:v","libx264","-preset","medium","-crf","23","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-ar","48000","-ac","2",n]
        else:
            cmd = ["ffmpeg","-y","-i",p,"-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=48000","-vf",vf,"-c:v","libx264","-preset","medium","-crf","23","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-map","0:v:0","-map","1:a:0","-shortest",n]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0: return False, f"Error {l}: {r.stderr[-300:]}"
        norms.append(n)
    if cb: cb("Combining...")
    cf = os.path.join(wd, "concat.txt")
    with open(cf,"w") as f:
        for n in norms: f.write(f"file '{n}'\n")
    r = subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",cf,"-c","copy",output], capture_output=True, text=True, timeout=600)
    if r.returncode != 0: return False, f"Concat error: {r.stderr[-300:]}"
    if cb: cb("Done!")
    return True, "Videos combined"

# ─── Session State ───────────────────────────────────────────────────────────
for k,v in {"intro_file":None,"main_file":None,"outro_file":None,"combined_file":None,"notebook_id":None,"pdf_path":None,"is_authenticated":None,"is_installed":None,"video_generated":False,"nlm_video_path":None}.items():
    if k not in st.session_state: st.session_state[k] = v

# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown('<div class="app-header"><h1>🎬 NotebookLM Video Studio</h1><p>Upload PDF → Auto-generate Video Overview via NotebookLM → Add Intro & Outro → Download Final Video</p></div>', unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔌 Connection Status")
    if st.session_state.is_installed is None: st.session_state.is_installed = check_installed()
    if st.session_state.is_installed:
        st.markdown("✅ `notebooklm-py` installed")
        if st.session_state.is_authenticated is None:
            with st.spinner("Checking auth..."): st.session_state.is_authenticated = check_auth()
        if st.session_state.is_authenticated:
            st.markdown('<span class="status-connected">🟢 Connected to NotebookLM</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-disconnected">🔴 Not logged in</span>', unsafe_allow_html=True)
            st.markdown(f"Login from terminal:\n```\n$env:NOTEBOOKLM_HOME = \"{NOTEBOOKLM_HOME}\"\nnotebooklm login\n```")
    else:
        st.markdown('<span class="status-disconnected">❌ notebooklm-py not found</span>', unsafe_allow_html=True)
        st.code('pip install "notebooklm-py[browser]"\nplaywright install chromium', language="bash")
    if st.button("🔄 Re-check Connection", use_container_width=True):
        st.session_state.is_installed = None; st.session_state.is_authenticated = None; st.rerun()
    st.divider(); st.markdown("### ⚙️ Output Settings")
    st.caption(f"📁 NOTEBOOKLM_HOME: `{NOTEBOOKLM_HOME}`")
    resolution = st.selectbox("Resolution", ["1920x1080 (Full HD)","1280x720 (HD)","3840x2160 (4K)"], index=0)
    target_res = resolution.split(" ")[0]
    target_fps = st.selectbox("FPS", [24,30,60], index=1)
    st.divider(); st.markdown("### 🎨 NotebookLM Style")
    video_style = st.selectbox("Visual Style", ["classic","whiteboard","watercolor","retro-print","heritage","paper-craft","kawaii","anime","auto"], index=0)
    st.divider()
    if st.button("🗑️ Reset All", use_container_width=True):
        wd = get_work_dir() if "work_dir" in st.session_state else None
        if wd and os.path.exists(wd): shutil.rmtree(wd, ignore_errors=True)
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

# ═══════ STEP 1 ══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">1</span><h3 style="margin:0;">Upload PDF & Create NotebookLM Notebook</h3></div>', unsafe_allow_html=True)
c1, c2 = st.columns([2,1])
with c1:
    pdf_file = st.file_uploader("Upload PDF document", type=["pdf"], key="pdf_uploader")
    if pdf_file:
        pdf_path = save_uploaded_file(pdf_file, pdf_file.name)
        st.session_state.pdf_path = pdf_path
        st.success(f"✅ **{pdf_file.name}** ({pdf_file.size/1024:.0f} KB)")
        notebook_title = st.text_input("Notebook Title", value=pdf_file.name.replace(".pdf","").replace("_"," ").title())
        if st.session_state.is_authenticated:
            if st.session_state.notebook_id is None:
                if st.button("📚 Create Notebook & Upload PDF", use_container_width=True, type="primary"):
                    with st.spinner("Creating notebook..."):
                        ok, nb_id, msg = create_notebook(notebook_title)
                    if ok and nb_id:
                        st.success(f"✅ Notebook: `{nb_id}`")
                        st.session_state.notebook_id = nb_id
                        with st.spinner("Uploading PDF (may take a minute)..."):
                            sok, smsg = add_pdf_source(nb_id, pdf_path)
                        if sok:
                            st.success("✅ PDF uploaded!"); time.sleep(1); st.rerun()
                        else: st.error(smsg)
                    else: st.error(msg)
            else:
                st.markdown(f'<div class="success-box">✅ Notebook ready — <code>{st.session_state.notebook_id}</code></div>', unsafe_allow_html=True)
        elif st.session_state.is_installed: st.warning("⚠️ Login first (see sidebar)")
        else: st.warning("⚠️ Install notebooklm-py first (see sidebar)")
with c2:
    st.markdown('<div class="info-box">📄 <strong>Flow:</strong><br><br>1. PDF uploaded locally<br>2. Notebook created<br>3. PDF added as source<br>4. Ready for video</div>', unsafe_allow_html=True)

# ═══════ STEP 2 ══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">2</span><h3 style="margin:0;">Generate Video Overview</h3></div>', unsafe_allow_html=True)
if st.session_state.notebook_id:
    steering = st.text_area("Steering Prompt", value="Create a comprehensive video overview covering all major topics and key concepts. Use clear, engaging explanations. Include timelines and diagrams. End with key takeaways.", height=100)
    st.caption(f"🎨 Style: **{video_style}** | ⏱️ ~3-10 minutes")
    if not st.session_state.video_generated:
        if st.button("🎬 Generate Video Overview", use_container_width=True, type="primary"):
            status = st.empty(); prog = st.progress(0)
            status.info("⏳ Generating... (3-10 min)"); prog.progress(15)
            ok, msg = generate_video(st.session_state.notebook_id, style=video_style if video_style != "auto" else None, prompt=steering.strip() or None)
            if ok:
                prog.progress(70); status.success("✅ Generated! Downloading...")
                vout = os.path.join(get_work_dir(), "overview.mp4")
                dok, dp, dm = download_video(st.session_state.notebook_id, vout)
                if dok:
                    prog.progress(100); st.session_state.nlm_video_path = dp; st.session_state.main_file = dp; st.session_state.video_generated = True; time.sleep(1); st.rerun()
                else: prog.progress(100); status.error(f"❌ Download: {dm}")
            else: prog.progress(100); status.error(f"❌ {msg}")
    else:
        st.markdown('<div class="success-box">✅ Video generated!</div>', unsafe_allow_html=True)
        if st.session_state.nlm_video_path and os.path.exists(st.session_state.nlm_video_path):
            vc1, vc2 = st.columns([2,1])
            with vc1: st.video(st.session_state.nlm_video_path)
            with vc2:
                vi = get_video_info(st.session_state.nlm_video_path)
                st.metric("Duration", vi["duration_str"]); st.metric("Resolution", f"{vi['width']}×{vi['height']}"); st.metric("Size", f"{vi['size_mb']:.1f} MB")
        if st.button("🔄 Regenerate"): st.session_state.video_generated = False; st.session_state.nlm_video_path = None; st.session_state.main_file = None; st.rerun()
else:
    st.markdown('<div class="step-card"><p style="text-align:center;color:#9ca3af;padding:1.5rem 0;">⬆️ Complete Step 1 first</p></div>', unsafe_allow_html=True)
    with st.expander("📂 Or upload a NotebookLM video manually"):
        manual = st.file_uploader("Upload video", type=["mp4","mov","avi","mkv","webm"], key="manual_vid")
        if manual:
            p = save_uploaded_file(manual, f"main_{manual.name}"); st.session_state.main_file = p; st.session_state.video_generated = True; st.session_state.nlm_video_path = p; st.success(f"✅ {manual.name}")

# ═══════ STEP 3 ══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">3</span><h3 style="margin:0;">Add Intro & Outro Videos</h3></div>', unsafe_allow_html=True)
ci, co = st.columns(2)
with ci:
    st.markdown("#### 🎬 Intro Video"); st.caption("Optional — plays before overview")
    iuf = st.file_uploader("intro", type=["mp4","mov","avi","mkv","webm"], key="intro_up", label_visibility="collapsed")
    if iuf:
        ip = save_uploaded_file(iuf, f"intro_{iuf.name}"); st.session_state.intro_file = ip; st.video(iuf)
        ii = get_video_info(ip); st.caption(f"{ii['duration_str']} | {ii['width']}×{ii['height']} | {ii['size_mb']:.1f} MB")
with co:
    st.markdown("#### 🎬 Outro Video"); st.caption("Optional — plays after overview")
    ouf = st.file_uploader("outro", type=["mp4","mov","avi","mkv","webm"], key="outro_up", label_visibility="collapsed")
    if ouf:
        op = save_uploaded_file(ouf, f"outro_{ouf.name}"); st.session_state.outro_file = op; st.video(ouf)
        oi = get_video_info(op); st.caption(f"{oi['duration_str']} | {oi['width']}×{oi['height']} | {oi['size_mb']:.1f} MB")

# ═══════ STEP 4 ══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">4</span><h3 style="margin:0;">Combine & Download Final Video</h3></div>', unsafe_allow_html=True)
hi = st.session_state.get("intro_file") is not None
hm = st.session_state.get("main_file") is not None
ho = st.session_state.get("outro_file") is not None
if hm:
    pi, td = [], 0
    if hi: vi=get_video_info(st.session_state.intro_file); td+=vi["duration"]; pi.append(f"🎬 Intro ({vi['duration_str']})")
    vi=get_video_info(st.session_state.main_file); td+=vi["duration"]; pi.append(f"📺 Overview ({vi['duration_str']})")
    if ho: vi=get_video_info(st.session_state.outro_file); td+=vi["duration"]; pi.append(f"🎬 Outro ({vi['duration_str']})")
    ts = f"{int(td//60)}:{int(td%60):02d}"
    st.markdown(f'<div class="step-card active"><strong>📎 Timeline:</strong>&nbsp;&nbsp;{"&nbsp;→&nbsp;".join(pi)}&nbsp;&nbsp;|&nbsp;&nbsp;<strong>Total: {ts}</strong></div>', unsafe_allow_html=True)
    oname = st.text_input("Filename", value=f"Final_Video_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    if hi or ho:
        if st.button("🚀 Combine Videos", use_container_width=True, type="primary"):
            opath = os.path.join(get_work_dir(), f"{oname}.mp4"); s=st.empty(); b=st.progress(0); b.progress(10)
            ok, msg = combine_videos(st.session_state.get("intro_file"), st.session_state.get("main_file"), st.session_state.get("outro_file"), opath, target_res, target_fps, lambda m: s.info(f"⏳ {m}"))
            b.progress(100)
            if ok and os.path.exists(opath): st.session_state.combined_file = opath; s.success(f"✅ {msg}"); st.rerun()
            else: s.error(f"❌ {msg}")
    else: st.session_state.combined_file = st.session_state.main_file
    final = st.session_state.get("combined_file")
    if final and os.path.exists(final):
        st.markdown("---"); st.markdown("### ✅ Final Video Ready!")
        fi = get_video_info(final)
        c1,c2,c3,c4 = st.columns(4); c1.metric("Duration",fi["duration_str"]); c2.metric("Resolution",f"{fi['width']}×{fi['height']}"); c3.metric("Size",f"{fi['size_mb']:.1f} MB"); c4.metric("FPS",f"{fi['fps']:.0f}")
        st.video(final)
        with open(final,"rb") as f: st.download_button(f"⬇️ Download ({fi['size_mb']:.1f} MB)", f.read(), f"{oname}.mp4", "video/mp4", use_container_width=True)
else:
    st.markdown('<div class="step-card"><p style="text-align:center;color:#9ca3af;padding:2rem 0;">⬆️ Generate or upload a video first (Steps 1-2)</p></div>', unsafe_allow_html=True)

st.markdown('---\n<div style="text-align:center;padding:1rem;color:#9ca3af;font-size:0.85rem;">🎬 NotebookLM Video Studio &bull; <a href="https://github.com/teng-lin/notebooklm-py">notebooklm-py</a> + Streamlit + FFmpeg</div>', unsafe_allow_html=True)
