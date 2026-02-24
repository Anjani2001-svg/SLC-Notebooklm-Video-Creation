import streamlit as st
import subprocess
import os
import re
import tempfile
import shutil
import json
import zipfile
import time
import base64
from datetime import datetime
from pathlib import Path

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="NotebookLM Video Studio", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

# ─── Config from env / secrets ───────────────────────────────────────────────
def get_config(key, default=""):
    """Get config from Streamlit secrets or environment variables."""
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except:
        return os.environ.get(key, default)

APP_PASSWORD = get_config("APP_PASSWORD", "")
NOTEBOOKLM_AUTH_JSON = get_config("NOTEBOOKLM_AUTH_JSON", "")
ADMIN_PASSWORD = get_config("ADMIN_PASSWORD", "")
NOTEBOOKLM_HOME = get_config("NOTEBOOKLM_HOME", "/tmp/notebooklm")

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container { padding-top: 1.5rem; max-width: 1300px; }
    .app-header { background: linear-gradient(135deg, #0f9b8e 0%, #1a56db 100%); padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem; color: white; }
    .app-header h1 { color: white !important; font-size: 2rem !important; margin-bottom: 0.3rem !important; }
    .app-header p { color: rgba(255,255,255,0.85); font-size: 1.05rem; margin: 0; }
    .step-badge { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 50%; background: #0f9b8e; color: white; font-weight: 700; font-size: 0.9rem; margin-right: 0.75rem; }
    .step-card { background: #f8f9fb; border: 1px solid #e2e6ed; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
    .step-card.active { border-color: #0f9b8e; background: #f0fdf9; }
    .info-box { background: #eff6ff; border-left: 4px solid #3b82f6; padding: 1rem 1.25rem; border-radius: 0 8px 8px 0; margin: 1rem 0; font-size: 0.95rem; }
    .success-box { background: #f0fdf4; border-left: 4px solid #22c55e; padding: 1rem 1.25rem; border-radius: 0 8px 8px 0; margin: 1rem 0; }
    .warning-box { background: #fffbeb; border-left: 4px solid #f59e0b; padding: 1rem 1.25rem; border-radius: 0 8px 8px 0; margin: 1rem 0; }
    .stat-row { display: flex; gap: 1rem; margin: 1rem 0; }
    .stat-card { flex: 1; background: white; border: 1px solid #e2e6ed; border-radius: 10px; padding: 1rem; text-align: center; }
    .stat-card .val { font-size: 1.8rem; font-weight: 700; color: #0f9b8e; }
    .stat-card .lbl { font-size: 0.85rem; color: #6b7280; }
    .login-container { max-width: 400px; margin: 100px auto; padding: 2rem; background: white; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.1); }
    .status-connected { color: #22c55e; font-weight: 600; }
    .status-disconnected { color: #ef4444; font-weight: 600; }
    .stDownloadButton > button { background: linear-gradient(135deg, #0f9b8e 0%, #1a56db 100%) !important; color: white !important; border: none !important; border-radius: 10px !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─── Password Gate ───────────────────────────────────────────────────────────
def check_password():
    """Returns True if no password set or user authenticated."""
    if not APP_PASSWORD:
        return True
    if st.session_state.get("authenticated"):
        return True
    return False

def show_login():
    st.markdown('<div class="app-header"><h1>🎬 NotebookLM Video Studio</h1><p>Team video generation tool</p></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("### 🔐 Team Login")
        pwd = st.text_input("Enter team password", type="password", key="login_pwd")
        if st.button("Login", use_container_width=True, type="primary"):
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")

# ─── Auth Setup ──────────────────────────────────────────────────────────────
def setup_auth():
    """Ensure NotebookLM auth is configured from env var."""
    home = NOTEBOOKLM_HOME
    os.makedirs(home, exist_ok=True)
    storage_path = os.path.join(home, "storage_state.json")

    # Write auth JSON from env/secrets if file doesn't exist or is empty
    if NOTEBOOKLM_AUTH_JSON and NOTEBOOKLM_AUTH_JSON.strip():
        try:
            auth_data = json.loads(NOTEBOOKLM_AUTH_JSON)
            with open(storage_path, "w") as f:
                json.dump(auth_data, f)
            return True
        except json.JSONDecodeError:
            # Maybe it's base64 encoded
            try:
                decoded = base64.b64decode(NOTEBOOKLM_AUTH_JSON).decode("utf-8")
                auth_data = json.loads(decoded)
                with open(storage_path, "w") as f:
                    json.dump(auth_data, f)
                return True
            except:
                return False
    elif os.path.exists(storage_path) and os.path.getsize(storage_path) > 10:
        return True

    return False

# ─── NLM CLI Wrapper ─────────────────────────────────────────────────────────
UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)

def get_nlm_env():
    env = os.environ.copy()
    env["NOTEBOOKLM_HOME"] = NOTEBOOKLM_HOME
    return env

def run_nlm(args, timeout=300):
    try:
        r = subprocess.run(["notebooklm"] + args, capture_output=True, text=True, timeout=timeout, env=get_nlm_env())
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return False, "", "notebooklm-py not installed"
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def check_installed():
    ok, _, _ = run_nlm(["--version"], timeout=10); return ok

def check_auth():
    ok, _, _ = run_nlm(["list"], timeout=30); return ok

# ─── Video Helpers ───────────────────────────────────────────────────────────
def get_work_dir():
    if "work_dir" not in st.session_state:
        st.session_state.work_dir = tempfile.mkdtemp(prefix="nblm_batch_")
    return st.session_state.work_dir

def save_upload(f, name):
    p = os.path.join(get_work_dir(), name)
    with open(p, "wb") as fh: fh.write(f.getbuffer())
    return p

def vid_info(path):
    try:
        r = subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format","-show_streams",path], capture_output=True, text=True, timeout=30)
        d = json.loads(r.stdout); dur = float(d.get("format",{}).get("duration",0))
        vs = next((s for s in d.get("streams",[]) if s["codec_type"]=="video"), {})
        au = next((s for s in d.get("streams",[]) if s["codec_type"]=="audio"), {})
        fps_s = vs.get("r_frame_rate","0/1")
        fps = eval(fps_s) if "/" in fps_s else float(fps_s)
        return {"duration":dur,"duration_str":f"{int(dur//60)}:{int(dur%60):02d}","width":int(vs.get("width",0)),"height":int(vs.get("height",0)),"fps":fps,"has_audio":bool(au),"size_mb":os.path.getsize(path)/(1024*1024)}
    except:
        return {"duration":0,"duration_str":"0:00","width":0,"height":0,"fps":0,"has_audio":False,"size_mb":0}

def combine_videos(intro, main, outro, output, res="1920x1080", fps=30):
    parts, labels = [], []
    if intro and os.path.exists(intro): parts.append(intro); labels.append("intro")
    if main and os.path.exists(main): parts.append(main); labels.append("main")
    if outro and os.path.exists(outro): parts.append(outro); labels.append("outro")
    if not parts: return False, "No files"
    if len(parts) == 1: shutil.copy2(parts[0], output); return True, "OK"
    wd = get_work_dir(); w, h = res.split("x"); norm = []
    for i, (p, l) in enumerate(zip(parts, labels)):
        n = os.path.join(wd, f"norm_{l}_{i}_{int(time.time())}.mp4"); info = vid_info(p)
        if info.get("has_audio"):
            cmd = ["ffmpeg","-y","-i",p,"-vf",f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps={fps}","-c:v","libx264","-preset","fast","-crf","23","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-ar","48000","-ac","2",n]
        else:
            cmd = ["ffmpeg","-y","-i",p,"-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=48000","-vf",f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,fps={fps}","-c:v","libx264","-preset","fast","-crf","23","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-map","0:v:0","-map","1:a:0","-shortest",n]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0: return False, f"FFmpeg error ({l})"
        norm.append(n)
    cf = os.path.join(wd, f"concat_{int(time.time())}.txt")
    with open(cf, "w") as f:
        for p in norm: f.write(f"file '{p}'\n")
    r = subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",cf,"-c","copy",output], capture_output=True, text=True, timeout=600)
    if r.returncode != 0: return False, "Concat error"
    return True, "OK"

def process_single_pdf(pdf_path, pdf_name, intro_path, outro_path, style, prompt, res, fps, status_cb):
    wd = get_work_dir()
    safe_name = re.sub(r'[^\w\-.]', '_', pdf_name.replace('.pdf', ''))

    status_cb("Creating notebook...")
    title = pdf_name.replace(".pdf", "").replace("_", " ").title()
    ok, out, err = run_nlm(["create", title], timeout=60)
    m = UUID_RE.search(out + "\n" + err)
    if not m: return False, None, f"Create failed: {err}"
    nb_id = m.group(0)

    status_cb("Selecting notebook...")
    run_nlm(["use", nb_id], timeout=30)

    status_cb("Uploading PDF...")
    ok, out, err = run_nlm(["source", "add", pdf_path], timeout=180)
    if not ok: return False, None, f"Source add: {err}"

    status_cb("Waiting for processing...")
    time.sleep(5)

    status_cb("Generating video (3-10 min)...")
    cmd = ["generate", "video", "--wait"]
    if style and style != "auto": cmd.extend(["--style", style])
    if prompt: cmd.append(prompt)
    ok, out, err = run_nlm(cmd, timeout=900)
    if not ok: return False, None, f"Generate: {err}"

    status_cb("Downloading video...")
    raw = os.path.join(wd, f"raw_{safe_name}.mp4")
    ok, out, err = run_nlm(["download", "video", raw], timeout=300)
    if not ok or not os.path.exists(raw): return False, None, f"Download: {err}"

    if intro_path or outro_path:
        status_cb("Adding intro/outro...")
        final = os.path.join(wd, f"final_{safe_name}.mp4")
        ok, msg = combine_videos(intro_path, raw, outro_path, final, res, fps)
        if not ok: return False, None, f"Combine: {msg}"
        return True, final, ""
    return True, raw, ""


# ─── Session State ───────────────────────────────────────────────────────────
for k, v in {"queue":[],"intro_file":None,"outro_file":None,"is_installed":None,"is_authenticated":None,"auth_setup":None}.items():
    if k not in st.session_state: st.session_state[k] = v


# ═══════════════ PASSWORD CHECK ══════════════════════════════════════════════
if not check_password():
    show_login()
    st.stop()

# ═══════════════ AUTH SETUP ══════════════════════════════════════════════════
if st.session_state.auth_setup is None:
    st.session_state.auth_setup = setup_auth()

# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown('<div class="app-header"><h1>🎬 NotebookLM Video Studio — Batch Mode</h1><p>Upload multiple PDFs → Queue auto-processes → Download all videos</p></div>', unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔌 Connection")
    if st.session_state.is_installed is None: st.session_state.is_installed = check_installed()
    if st.session_state.is_installed:
        st.markdown("✅ `notebooklm-py`")
        if st.session_state.is_authenticated is None: st.session_state.is_authenticated = check_auth()
        if st.session_state.is_authenticated:
            st.markdown('<span class="status-connected">🟢 Connected</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-disconnected">🔴 Auth expired</span>', unsafe_allow_html=True)
            st.markdown("""
            <div class="warning-box">
                Session expired. Admin needs to update <code>NOTEBOOKLM_AUTH_JSON</code> in secrets.
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 Re-check", key="rc"): st.session_state.is_authenticated = None; st.session_state.auth_setup = None; st.rerun()
    else:
        st.markdown("❌ notebooklm-py not installed on server")

    st.divider()
    st.markdown("### ⚙️ Settings")
    resolution = st.selectbox("Resolution", ["1920x1080 (Full HD)","1280x720 (HD)","3840x2160 (4K)"])
    target_res = resolution.split(" ")[0]
    target_fps = st.selectbox("FPS", [24,30,60], index=1)

    st.divider()
    st.markdown("### 🎨 Style")
    video_style = st.selectbox("Visual Style", ["classic","whiteboard","watercolor","retro-print","heritage","paper-craft","kawaii","anime","auto"])

    st.divider()
    st.markdown("### 📝 Prompt")
    global_prompt = st.text_area("Applied to all", value="Create a comprehensive video overview of all major topics. Use clear explanations with timelines and diagrams. End with key takeaways.", height=100, key="gp")

    # Admin section
    st.divider()
    st.markdown("### 🔧 Admin")
    with st.expander("Update Auth (admin only)"):
        admin_pwd = st.text_input("Admin password", type="password", key="admin_pwd")
        new_auth = st.text_area("Paste storage_state.json content", height=100, key="new_auth")
        if st.button("Update Auth", key="update_auth"):
            if ADMIN_PASSWORD and admin_pwd == ADMIN_PASSWORD:
                try:
                    data = json.loads(new_auth)
                    home = NOTEBOOKLM_HOME
                    os.makedirs(home, exist_ok=True)
                    with open(os.path.join(home, "storage_state.json"), "w") as f:
                        json.dump(data, f)
                    st.session_state.is_authenticated = None
                    st.session_state.auth_setup = None
                    st.success("✅ Auth updated! Click Re-check.")
                except:
                    st.error("Invalid JSON")
            elif not ADMIN_PASSWORD:
                st.error("Set ADMIN_PASSWORD in secrets first")
            else:
                st.error("Wrong admin password")

    q = st.session_state.queue
    done = sum(1 for i in q if i["status"] == "done")
    st.caption(f"Queue: {len(q)} | Done: {done}")

    if st.button("🗑️ Reset", use_container_width=True):
        wd = st.session_state.get("work_dir")
        if wd and os.path.exists(wd): shutil.rmtree(wd, ignore_errors=True)
        for k in list(st.session_state.keys()):
            if k != "authenticated": del st.session_state[k]
        st.rerun()


# ═══════════════ STEP 1: Intro & Outro ═══════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">1</span><h3 style="margin:0;">Set Intro & Outro (applied to all)</h3></div>', unsafe_allow_html=True)

ci, co, cinfo = st.columns([1, 1, 1])
with ci:
    st.markdown("**🎬 Intro** (optional)")
    inf = st.file_uploader("intro", type=["mp4","mov","avi","mkv","webm"], key="int_up", label_visibility="collapsed")
    if inf:
        ip = save_upload(inf, f"intro_{inf.name}"); st.session_state.intro_file = ip
        st.video(inf); ii = vid_info(ip); st.caption(f"✅ {ii['duration_str']}")
    elif st.session_state.intro_file:
        st.caption(f"✅ Intro loaded")
with co:
    st.markdown("**🎬 Outro** (optional)")
    ouf = st.file_uploader("outro", type=["mp4","mov","avi","mkv","webm"], key="out_up", label_visibility="collapsed")
    if ouf:
        op = save_upload(ouf, f"outro_{ouf.name}"); st.session_state.outro_file = op
        st.video(ouf); oi = vid_info(op); st.caption(f"✅ {oi['duration_str']}")
    elif st.session_state.outro_file:
        st.caption(f"✅ Outro loaded")
with cinfo:
    hi = "✅" if st.session_state.intro_file else "—"
    ho = "✅" if st.session_state.outro_file else "—"
    st.markdown(f'<div class="info-box">Intro: {hi} | Outro: {ho}<br>Style: {video_style} | {target_res} @ {target_fps}fps</div>', unsafe_allow_html=True)


# ═══════════════ STEP 2: Upload PDFs ═════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">2</span><h3 style="margin:0;">Add PDFs to Queue</h3></div>', unsafe_allow_html=True)

pdfs = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True, key="pdf_batch")
if pdfs:
    existing = {i["name"] for i in st.session_state.queue}
    added = 0
    for pdf in pdfs:
        if pdf.name not in existing:
            pp = save_upload(pdf, pdf.name)
            st.session_state.queue.append({"name":pdf.name,"path":pp,"status":"pending","output":None,"error":"","nb_id":None})
            added += 1
    if added: st.success(f"✅ Added {added} PDF(s)"); st.rerun()


# ═══════════════ STEP 3: Queue ═══════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">3</span><h3 style="margin:0;">Processing Queue</h3></div>', unsafe_allow_html=True)

queue = st.session_state.queue
if not queue:
    st.markdown('<div style="text-align:center;color:#9ca3af;padding:2rem;">📂 Empty — upload PDFs above</div>', unsafe_allow_html=True)
else:
    total = len(queue)
    pending = sum(1 for i in queue if i["status"]=="pending")
    done = sum(1 for i in queue if i["status"]=="done")
    errors = sum(1 for i in queue if i["status"]=="error")
    proc = sum(1 for i in queue if i["status"]=="processing")

    st.markdown(f'<div class="stat-row"><div class="stat-card"><div class="val">{total}</div><div class="lbl">Total</div></div><div class="stat-card"><div class="val">{pending}</div><div class="lbl">⏳ Pending</div></div><div class="stat-card"><div class="val">{proc}</div><div class="lbl">🔄 Active</div></div><div class="stat-card"><div class="val">{done}</div><div class="lbl">✅ Done</div></div><div class="stat-card"><div class="val">{errors}</div><div class="lbl">❌ Failed</div></div></div>', unsafe_allow_html=True)

    if total > 0: st.progress(done / total, text=f"{done}/{total}")

    for idx, item in enumerate(queue):
        icon = {"pending":"⏳","processing":"🔄","done":"✅","error":"❌"}.get(item["status"],"?")
        cs, cn, ca = st.columns([0.5, 3, 1.5])
        with cs: st.markdown(f"### {icon}")
        with cn:
            st.markdown(f"**{item['name']}**")
            if item["status"]=="done" and item["output"]:
                vi = vid_info(item["output"]); st.caption(f"✅ {vi['duration_str']} | {vi['size_mb']:.1f} MB")
            elif item["status"]=="error": st.caption(f"❌ {item['error'][:100]}")
            elif item["status"]=="pending": st.caption("Waiting...")
        with ca:
            if item["status"]=="done" and item["output"] and os.path.exists(item["output"]):
                with open(item["output"],"rb") as f:
                    st.download_button("⬇️", f.read(), f"{item['name'].replace('.pdf','')}_video.mp4", "video/mp4", key=f"dl_{idx}", use_container_width=True)
            elif item["status"]=="error":
                if st.button("🔄 Retry", key=f"re_{idx}", use_container_width=True):
                    st.session_state.queue[idx]["status"]="pending"; st.session_state.queue[idx]["error"]=""; st.rerun()
            elif item["status"]=="pending":
                if st.button("🗑️", key=f"rm_{idx}", use_container_width=True):
                    st.session_state.queue.pop(idx); st.rerun()

    st.markdown("---")
    b1, b2, b3 = st.columns([2,1,1])
    with b1:
        if pending > 0 and st.session_state.is_authenticated:
            if st.button(f"🚀 Process All ({pending} PDFs)", use_container_width=True, type="primary"):
                bar = st.progress(0, text="Starting..."); cnt = 0
                for idx, item in enumerate(st.session_state.queue):
                    if item["status"] != "pending": continue
                    st.session_state.queue[idx]["status"] = "processing"
                    bar.progress(cnt/pending, text=f"{cnt+1}/{pending}: {item['name']}")
                    ist = st.empty(); ilog = st.empty()
                    def scb(msg): ist.info(f"📄 **{item['name']}** — {msg}")
                    try:
                        ok, outp, err = process_single_pdf(item["path"], item["name"], st.session_state.intro_file, st.session_state.outro_file, video_style if video_style!="auto" else None, global_prompt.strip() or None, target_res, target_fps, scb)
                        if ok:
                            st.session_state.queue[idx]["status"]="done"; st.session_state.queue[idx]["output"]=outp
                            ist.success(f"✅ **{item['name']}**")
                        else:
                            st.session_state.queue[idx]["status"]="error"; st.session_state.queue[idx]["error"]=err
                            ist.error(f"❌ **{item['name']}** — {err[:100]}")
                    except Exception as e:
                        st.session_state.queue[idx]["status"]="error"; st.session_state.queue[idx]["error"]=str(e)
                        ist.error(f"❌ {str(e)[:100]}")
                    cnt += 1
                bar.progress(1.0, text=f"✅ Done! {cnt} processed"); st.rerun()
        elif pending > 0:
            st.warning("⚠️ NotebookLM not connected")
    with b2:
        if done > 0:
            if st.button("🗑️ Clear Done", use_container_width=True):
                st.session_state.queue = [i for i in st.session_state.queue if i["status"]!="done"]; st.rerun()
    with b3:
        if queue:
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.queue = []; st.rerun()


# ═══════════════ STEP 4: Download ════════════════════════════════════════════
st.markdown("---")
st.markdown('<div style="display:flex;align-items:center;margin-bottom:1rem;"><span class="step-badge">4</span><h3 style="margin:0;">Download</h3></div>', unsafe_allow_html=True)

done_items = [i for i in queue if i["status"]=="done" and i["output"] and os.path.exists(i["output"])]
if done_items:
    st.markdown(f"**{len(done_items)} video(s) ready**")
    for idx, item in enumerate(done_items):
        with st.expander(f"📺 {item['name'].replace('.pdf','')}"):
            vi = vid_info(item["output"]); c1,c2 = st.columns([2,1])
            with c1: st.video(item["output"])
            with c2:
                st.metric("Duration", vi["duration_str"]); st.metric("Size", f"{vi['size_mb']:.1f} MB")
                with open(item["output"],"rb") as f:
                    st.download_button("⬇️ Download", f.read(), f"{item['name'].replace('.pdf','')}_video.mp4", "video/mp4", key=f"dlp_{idx}", use_container_width=True)
    if len(done_items) > 1:
        st.markdown("---")
        if st.button("📦 Download All as ZIP", use_container_width=True, type="primary"):
            zp = os.path.join(get_work_dir(), f"videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
            with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i in done_items: zf.write(i["output"], i["name"].replace(".pdf","_video.mp4"))
            with open(zp,"rb") as f:
                mb = sum(vid_info(i["output"])["size_mb"] for i in done_items)
                st.download_button(f"⬇️ ZIP ({mb:.1f} MB)", f.read(), os.path.basename(zp), "application/zip", key="dlz", use_container_width=True)
else:
    st.markdown('<div style="text-align:center;color:#9ca3af;padding:2rem;">No completed videos yet</div>', unsafe_allow_html=True)

st.markdown('---\n<div style="text-align:center;padding:1rem;color:#9ca3af;font-size:0.85rem;">🎬 NotebookLM Video Studio</div>', unsafe_allow_html=True)
