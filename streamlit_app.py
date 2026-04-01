"""
DermoAI — Streamlit Live Web App
All features: Auth, Skin Analysis, Grad-CAM, Wound Gate, XAI, History,
Doctor Listing, Appointment Scheduling, Notifications — backed by SQLite.
"""

import sys, os
# Make sure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "backend"))  # so SQL DB path resolves

import streamlit as st
import base64
import io
import uuid
import time
import numpy as np
import cv2
from PIL import Image
from datetime import datetime, timedelta
import torch
import torch.nn.functional as F
from sqlalchemy.orm import Session

# ── Internal imports ──────────────────────────────────────────────────────────
from app.database import SessionLocal, engine
from app import db_models, auth
from app.ml_model import load_model, CLASSES, Config
from app.gradcam import GradCAM, overlay_cam
from app.wound_model import load_wound_model, predict_wound
from app.report import generate_report

db_models.Base.metadata.create_all(bind=engine)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DermoAI — Clinical Skin Analysis",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #0f172a; color: #f8fafc; }

header[data-testid="stHeader"] { background: #0f172a; border-bottom: 1px solid #1e293b; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: 1px solid #1e293b;
}
[data-testid="stSidebar"] * { color: #f8fafc !important; }

/* Cards */
.dermocard {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}

/* Badges */
.badge-green  { background: rgba(16,185,129,.15); color:#34d399; border:1px solid rgba(16,185,129,.3); border-radius:20px; padding:4px 12px; font-size:12px; font-weight:700; }
.badge-red    { background: rgba(239,68,68,.15);  color:#f87171; border:1px solid rgba(239,68,68,.3);  border-radius:20px; padding:4px 12px; font-size:12px; font-weight:700; }
.badge-amber  { background: rgba(245,158,11,.15); color:#fbbf24; border:1px solid rgba(245,158,11,.3); border-radius:20px; padding:4px 12px; font-size:12px; font-weight:700; }
.badge-blue   { background: rgba(59,130,246,.15); color:#60a5fa; border:1px solid rgba(59,130,246,.3); border-radius:20px; padding:4px 12px; font-size:12px; font-weight:700; }

/* Headline */
.hero-title  { font-size:2.8rem; font-weight:900; background:linear-gradient(135deg,#3b82f6,#10b981); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.hero-sub    { color:#94a3b8; font-size:1.1rem; margin-top:6px; }

/* News card */
.news-card { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:16px; }
.news-source { color:#94a3b8; font-size:12px; }

/* Buttons override */
.stButton button {
    background: #3b82f6 !important;
    color: white !important;
    border-radius: 10px !important;
    border: none !important;
    font-weight: 600 !important;
    padding: 10px 20px !important;
}
.stButton button:hover { background: #2563eb !important; }

div[data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700 !important; color: #3b82f6 !important; }
</style>
""", unsafe_allow_html=True)

# ── DB helper ──────────────────────────────────────────────────────────────────
def get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        raise

# ── Model caching ──────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading AI models…")
def load_all_models():
    skin_model, skin_device = load_model()
    wound_model, wound_device, wound_num_classes = load_wound_model()
    return skin_model, skin_device, wound_model, wound_device, wound_num_classes

# ── Image transform ────────────────────────────────────────────────────────────
def transform_image(image_bytes):
    from torchvision import transforms
    skin_model, skin_device, *_ = load_all_models()
    t = transforms.Compose([
        transforms.Resize((Config.IMAGE_SIZE, Config.IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return t(img).unsqueeze(0).to(skin_device), img

# ── Grad-CAM helper ────────────────────────────────────────────────────────────
def run_gradcam(tensor, original_pil, class_idx):
    skin_model, skin_device, *_ = load_all_models()
    target_layer = None
    try:
        if hasattr(skin_model, 'local') and hasattr(skin_model.local, 'blocks'):
            last_block = skin_model.local.blocks[-1]
            if isinstance(last_block, torch.nn.Sequential) and len(last_block) > 0:
                target_layer = last_block[-2] if len(last_block) >= 2 else last_block[-1]
            else:
                target_layer = last_block
    except Exception:
        pass

    if target_layer is None:
        return None, None

    try:
        tensor_with_grad = tensor.clone().detach().requires_grad_(True)
        with GradCAM(skin_model, target_layer) as gcam:
            mask, _, _ = gcam(tensor_with_grad, class_idx)

        img_np = np.array(original_pil.resize((Config.IMAGE_SIZE, Config.IMAGE_SIZE)), dtype=np.float32) / 255.0
        cam_result = overlay_cam(img_np, mask, alpha=0.6)
        cam_result = (cam_result * 255).astype(np.uint8)
        cam_bgr = cv2.cvtColor(cam_result, cv2.COLOR_RGB2BGR)
        _, buf = cv2.imencode('.png', cam_bgr)
        heatmap_bytes = buf.tobytes()
        heatmap_b64 = base64.b64encode(heatmap_bytes).decode()
        return heatmap_b64, heatmap_bytes
    except Exception as e:
        st.warning(f"Grad-CAM skipped: {e}")
        return None, None

# ── Init session state ─────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "user": None,
        "page": "🔬 Analyze",
        "flash": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── Auth helpers ───────────────────────────────────────────────────────────────
def do_login(email, password):
    db = get_db()
    user = db.query(db_models.User).filter(db_models.User.email == email).first()
    db.close()
    if user and auth.verify_password(password, user.hashed_password):
        st.session_state.user = {
            "id": user.id, "email": user.email,
            "role": user.role, "specialty": user.specialty,
            "achievement": user.achievement
        }
        return True
    return False

def do_register(email, password, role, specialty=None, achievement=None):
    db = get_db()
    exists = db.query(db_models.User).filter(db_models.User.email == email).first()
    if exists:
        db.close()
        return False, "Email already registered."
    hashed = auth.get_password_hash(password)
    user = db_models.User(email=email, hashed_password=hashed,
                          role=role, specialty=specialty, achievement=achievement)
    db.add(user)
    db.commit()
    db.close()
    return True, "Registered! Please log in."

# ══════════════════════════════════════════════════════════════════════════════
# AUTH PAGE
# ══════════════════════════════════════════════════════════════════════════════
def auth_page():
    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        st.markdown('<div class="hero-title">🧬 DermoAI</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-sub">AI-powered clinical skin analysis platform</div>', unsafe_allow_html=True)
        st.markdown('<div class="badge-green" style="margin:12px 0 24px 0">🤝 In collaboration with Global Dermatology Institute</div>', unsafe_allow_html=True)

        tab_login, tab_reg = st.tabs(["Login", "Register"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login →", use_container_width=True)
                if submitted:
                    if do_login(email, password):
                        st.success("Welcome back!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Check email/password.")

        with tab_reg:
            with st.form("reg_form"):
                r_email = st.text_input("Email", placeholder="you@example.com", key="re")
                r_pass = st.text_input("Password", type="password", key="rp")
                r_role = st.selectbox("Role", ["patient", "doctor"])
                r_specialty, r_achieve = "", ""
                if r_role == "doctor":
                    r_specialty = st.text_input("Specialty", key="rs")
                    r_achieve = st.text_input("Achievements", key="ra")
                reg_sub = st.form_submit_button("Create Account", use_container_width=True)
                if reg_sub:
                    ok, msg = do_register(r_email, r_pass, r_role, r_specialty, r_achieve)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS PAGE
# ══════════════════════════════════════════════════════════════════════════════
CLINICAL_NEWS = [
    {"title": "Breakthrough in Non-Invasive Melanoma Screening", "src": "Global Dermatology Foundation", "date": "2h ago", "link": "https://www.aad.org"},
    {"title": "AI Model Surpasses Expert Dermatologists in BCC Detection", "src": "Nature Medicine", "date": "1d ago", "link": "https://www.nature.com"},
    {"title": "New WHO Guidelines for Pediatric Skin Risk Assessment", "src": "WHO Dermatology", "date": "3d ago", "link": "https://www.who.int"},
    {"title": "Advances in Dermoscopic Deep Learning for Rare Lesions", "src": "JAAD Online", "date": "1w ago", "link": "https://www.jaad.org"},
]

def analyze_page():
    user = st.session_state.user
    skin_model, skin_device, wound_model, wound_device, wound_num_classes = load_all_models()

    # ── Collab Badge ──────────────────────────────────────────────────────────
    st.markdown('<div class="badge-green">🛡️ In collaboration with Global Dermatology Institute</div>', unsafe_allow_html=True)
    st.markdown("## 🔬 Instant Clinical Skin Analysis")
    st.caption("Upload a clear dermoscopic or smartphone lesion photo for AI evaluation.")

    col_upload, col_news = st.columns([1.3, 1])

    with col_upload:
        with st.container():
            st.markdown('<div class="dermocard">', unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload your skin image", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
            if uploaded:
                st.image(uploaded, caption="Uploaded image", use_container_width=True)
            analyze = st.button("⚡ Run AI Diagnostics", use_container_width=True, disabled=(uploaded is None))
            st.markdown('</div>', unsafe_allow_html=True)

    with col_news:
        st.markdown("#### 📰 Clinical Research Feed")
        for item in CLINICAL_NEWS:
            st.markdown(f"""
            <div class="news-card" style="margin-bottom:10px">
                <span class="badge-blue">{item['date']}</span>
                <p style="font-weight:600;margin:8px 0 4px 0;color:#f8fafc">{item['title']}</p>
                <span class="news-source">{item['src']}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Analysis ──────────────────────────────────────────────────────────────
    if analyze and uploaded:
        image_bytes = uploaded.read()
        with st.spinner("Running AI analysis pipeline…"):
            # 1. Wound gate
            is_wound, wound_label, wound_conf = predict_wound(wound_model, wound_device, wound_num_classes, image_bytes)

            if is_wound:
                st.markdown(f"""
                <div class="dermocard">
                    <span class="badge-amber">⚠️ Wound Detected</span>
                    <h2 style="margin:16px 0 4px 0">Wound Type: {wound_label.title()}</h2>
                    <p style="color:#94a3b8">Confidence: {wound_conf:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)
                report = generate_report(wound_label, wound_conf, image_bytes=image_bytes, wound_label=wound_label)
                _save_and_show_report(None, wound_label, wound_conf, report, None, image_bytes, is_wound=True)
            else:
                # 2. Skin lesion model
                tensor, pil_img = transform_image(image_bytes)
                with torch.no_grad():
                    outputs = skin_model(tensor)
                    probs = F.softmax(outputs, dim=1)
                    conf, pred_idx = torch.max(probs, 1)
                class_name = CLASSES[pred_idx.item()] if pred_idx.item() < len(CLASSES) else "Unknown"
                conf_score = conf.item() * 100

                # 3. Grad-CAM
                heatmap_b64, heatmap_bytes = run_gradcam(tensor, pil_img, pred_idx.item())

                # 4. XAI Report
                report = generate_report(class_name, conf_score, image_bytes=image_bytes)

                _save_and_show_report(heatmap_b64, class_name, conf_score, report, pil_img, image_bytes)


def _save_and_show_report(heatmap_b64, class_name, conf_score, report, pil_img, image_bytes, is_wound=False):
    user = st.session_state.user
    is_mal = class_name.lower() == "malignant" if not is_wound else False

    col_diag, col_heat = st.columns([1, 1])
    with col_diag:
        badge = "badge-red" if is_mal else ("badge-amber" if is_wound else "badge-green")
        risk  = "🔴 HIGH RISK" if is_mal else ("🟡 MODERATE" if is_wound else "🟢 LOW RISK")
        st.markdown(f"""
        <div class="dermocard">
            <span class="{badge}">{risk}</span>
            <h1 style="margin:16px 0 4px 0;font-size:2rem">{class_name.title()}</h1>
            <p style="color:#94a3b8">Confidence: {conf_score:.1f}%</p>
        </div>
        """, unsafe_allow_html=True)

    with col_heat:
        if heatmap_b64:
            st.image(base64.b64decode(heatmap_b64), caption="AI Grad-CAM Heatmap — regions that drove classification", use_container_width=True)
        else:
            st.info("Grad-CAM visualization not available for wound images.")

    # Report
    with st.expander("📋 Full Clinical Report", expanded=True):
        st.markdown(report)

    # Save to DB
    if user:
        db = get_db()
        UPLOAD_DIR = "uploads"; os.makedirs(UPLOAD_DIR, exist_ok=True)
        uid = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        img_path = os.path.join(UPLOAD_DIR, f"{uid}.jpg")
        with open(img_path, "wb") as f:
            f.write(image_bytes)
        new_pred = db_models.Prediction(
            user_id=user["id"], image_path=img_path,
            diagnosis=class_name, confidence=conf_score,
            report_text=report
        )
        db.add(new_pred)
        db.commit()
        db.close()
        st.success("✅ Analysis saved to your history.")


# ══════════════════════════════════════════════════════════════════════════════
# HISTORY PAGE
# ══════════════════════════════════════════════════════════════════════════════
def history_page():
    user = st.session_state.user
    st.markdown("## 📂 Your Analysis History")

    db = get_db()
    preds = db.query(db_models.Prediction)\
        .filter(db_models.Prediction.user_id == user["id"])\
        .order_by(db_models.Prediction.created_at.desc()).all()
    db.close()

    if not preds:
        st.info("No analysis history yet. Run your first scan on the Analyze page!")
        return

    for p in preds:
        is_mal = p.diagnosis.lower() == "malignant"
        badge = "badge-red" if is_mal else "badge-green"
        risk = "HIGH RISK" if is_mal else "LOW RISK"
        with st.expander(f"🗓 {p.created_at.strftime('%b %d, %Y %I:%M %p')}  |  **{p.diagnosis}**  |  {p.confidence:.1f}%"):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(f'<span class="{badge}">{risk}</span>', unsafe_allow_html=True)
                st.metric("Diagnosis", p.diagnosis)
                st.metric("Confidence", f"{p.confidence:.1f}%")
                st.metric("Status", p.status.upper())

                # Try to load heatmap
                if p.image_path:
                    base = os.path.splitext(os.path.basename(p.image_path))[0]
                    hm_path = os.path.join(os.path.dirname(p.image_path), f"{base}_heatmap.png")
                    if os.path.exists(hm_path):
                        st.image(hm_path, caption="Grad-CAM", use_container_width=True)
                    elif os.path.exists(p.image_path):
                        st.image(p.image_path, caption="Original", use_container_width=True)
            with c2:
                st.markdown("**Clinical Report:**")
                st.markdown(p.report_text or "_No report available._")


# ══════════════════════════════════════════════════════════════════════════════
# DOCTORS PAGE
# ══════════════════════════════════════════════════════════════════════════════
def doctors_page():
    user = st.session_state.user
    st.markdown("## 🩺 Available Dermatologists")
    st.caption("Schedule a consultation with a board-certified specialist.")

    db = get_db()
    doctors = db.query(db_models.User).filter(db_models.User.role == "doctor").all()
    db.close()

    if not doctors:
        st.info("No doctors registered yet.")
        return

    for doc in doctors:
        with st.container():
            st.markdown('<div class="dermocard">', unsafe_allow_html=True)
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.markdown(f"### 👨‍⚕️ Dr. {doc.email.split('@')[0].title()}")
                st.markdown(f"<span class='badge-blue'>{doc.specialty or 'General Dermatologist'}</span>", unsafe_allow_html=True)
                st.caption(doc.achievement or "Expert in skin lesion analysis.")
            with col_btn:
                if st.button(f"Schedule 📅", key=f"sched_{doc.id}"):
                    st.session_state[f"sched_doc"] = {"id": doc.id, "email": doc.email, "specialty": doc.specialty}
                    st.session_state[f"sched_open"] = True
            st.markdown('</div>', unsafe_allow_html=True)

    # Scheduling modal (expanded section)
    if st.session_state.get("sched_open"):
        doc = st.session_state["sched_doc"]
        st.markdown("---")
        st.markdown(f"### 📅 Book Appointment with Dr. {doc['email'].split('@')[0].title()}")
        today = datetime.now().date()
        selected_date = st.date_input("Select Date", min_value=today, max_value=today + timedelta(days=14))
        time_slots = ["10:00 AM", "11:00 AM", "12:00 PM", "02:00 PM", "03:00 PM", "04:00 PM"]
        selected_time = st.selectbox("Select Time Slot", time_slots)

        if st.button("✅ Confirm Appointment"):
            try:
                dt_str = f"{selected_date} {selected_time}"
                scheduled_at = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
                db = get_db()
                appt = db_models.Appointment(
                    patient_id=user["id"], doctor_id=doc["id"],
                    scheduled_at=scheduled_at
                )
                db.add(appt)
                notif = db_models.Notification(
                    user_id=doc["id"],
                    message=f"New appointment from {user['email']} on {selected_date} at {selected_time}."
                )
                db.add(notif)
                notif2 = db_models.Notification(
                    user_id=user["id"],
                    message=f"Your appointment with Dr. {doc['email'].split('@')[0]} is confirmed for {selected_date} at {selected_time}."
                )
                db.add(notif2)
                db.commit()
                db.close()
                st.success(f"Appointment confirmed for {selected_date} at {selected_time}!")
                st.session_state["sched_open"] = False
            except Exception as e:
                st.error(f"Booking failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# DOCTOR — PENDING CASES
# ══════════════════════════════════════════════════════════════════════════════
def cases_page():
    user = st.session_state.user
    st.markdown("## 📁 Pending Patient Cases")

    db = get_db()
    cases = db.query(db_models.Prediction)\
        .filter(db_models.Prediction.status == "pending")\
        .order_by(db_models.Prediction.created_at.desc()).all()
    db.close()

    if not cases:
        st.info("No pending cases at the moment.")
        return

    for case in cases:
        with st.expander(f"Patient #{case.user_id} — {case.diagnosis} ({case.created_at.strftime('%b %d, %Y')})"):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.metric("Diagnosis", case.diagnosis)
                st.metric("Confidence", f"{case.confidence:.1f}%")
                if case.image_path and os.path.exists(case.image_path):
                    st.image(case.image_path, caption="Patient Image", use_container_width=True)
            with col2:
                st.markdown("**AI Report:**")
                st.markdown(case.report_text or "_No report._")
                if st.button("✅ Accept Case", key=f"acc_{case.id}"):
                    db = get_db()
                    c = db.query(db_models.Prediction).filter(db_models.Prediction.id == case.id).first()
                    c.status = "accepted"
                    c.doctor_id = user["id"]
                    notif = db_models.Notification(
                        user_id=c.user_id,
                        message=f"Dr. {user['email']} has accepted your case."
                    )
                    db.add(notif)
                    db.commit()
                    db.close()
                    st.success("Case accepted!")
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS PAGE
# ══════════════════════════════════════════════════════════════════════════════
def notifications_page():
    user = st.session_state.user
    st.markdown("## 🔔 Notifications")

    db = get_db()
    notifs = db.query(db_models.Notification)\
        .filter(db_models.Notification.user_id == user["id"])\
        .order_by(db_models.Notification.created_at.desc()).all()

    # Mark all as read
    for n in notifs:
        if not n.is_read:
            n.is_read = 1
    db.commit()
    db.close()

    if not notifs:
        st.info("You have no notifications yet.")
        return

    for n in notifs:
        icon = "🔵" if not n.is_read else "⚪"
        st.markdown(f"""
        <div class="dermocard" style="padding:14px 20px">
            <span style="font-size:18px">{icon}</span>
            <span style="margin-left:12px;color:#f8fafc">{n.message}</span>
            <br><small style="color:#94a3b8">{n.created_at.strftime('%b %d, %Y %I:%M %p')}</small>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE PAGE
# ══════════════════════════════════════════════════════════════════════════════
def profile_page():
    user = st.session_state.user
    st.markdown("## 👤 Profile")

    db = get_db()
    u = db.query(db_models.User).filter(db_models.User.id == user["id"]).first()
    pred_count = db.query(db_models.Prediction).filter(db_models.Prediction.user_id == user["id"]).count()
    db.close()

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"""
        <div class="dermocard" style="text-align:center">
            <div style="font-size:5rem">👤</div>
            <h2 style="margin:12px 0 4px 0">{u.email.split('@')[0].title()}</h2>
            <span class="badge-blue">{u.role.upper()}</span>
            <p style="color:#94a3b8;margin-top:12px">{u.email}</p>
            <p style="color:#94a3b8">Member since {u.created_at.strftime('%b %Y')}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.metric("Total Analyses", pred_count)
        if u.role == "doctor":
            st.metric("Specialty", u.specialty or "—")
            st.metric("Achievements", u.achievement or "—")

        db = get_db()
        appts = db.query(db_models.Appointment)\
            .filter((db_models.Appointment.patient_id == user["id"]) |
                    (db_models.Appointment.doctor_id == user["id"]))\
            .order_by(db_models.Appointment.scheduled_at.desc()).limit(5).all()
        db.close()

        if appts:
            st.markdown("#### 📅 Recent Appointments")
            for a in appts:
                role_label = "with patient" if u.role == "doctor" else "with Dr."
                other_id = a.patient_id if u.role == "doctor" else a.doctor_id
                other_db = get_db()
                other = other_db.query(db_models.User).filter(db_models.User.id == other_id).first()
                other_name = other.email.split('@')[0].title() if other else "Unknown"
                other_db.close()
                st.markdown(f"- 🗓 {a.scheduled_at.strftime('%b %d, %Y %I:%M %p')} — {role_label} {other_name} `{a.status}`")

    if st.button("🚪 Logout"):
        st.session_state.user = None
        st.session_state.page = "🔬 Analyze"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown('<div style="font-size:1.5rem;font-weight:900;color:#3b82f6;">🧬 DermoAI</div>', unsafe_allow_html=True)
        st.caption(f"Signed in as **{user['email'].split('@')[0].title()}** · `{user['role']}`")
        st.divider()

        # Unread notifications count
        db = get_db()
        unread = db.query(db_models.Notification)\
            .filter(db_models.Notification.user_id == user["id"],
                    db_models.Notification.is_read == 0).count()
        db.close()

        # Pages per role
        if user["role"] == "patient":
            pages = ["🔬 Analyze", "📂 History", "🩺 Doctors",
                     f"🔔 Notifications{f' ({unread})' if unread else ''}", "👤 Profile"]
        else:
            pages = ["📁 Cases", "📂 History",
                     f"🔔 Notifications{f' ({unread})' if unread else ''}", "👤 Profile"]

        for p in pages:
            selected = st.sidebar.button(p, use_container_width=True, key=f"nav_{p}")
            if selected:
                # normalise name (strip unread count noise)
                st.session_state.page = p.split(" (")[0]
                st.rerun()

        st.divider()
        st.markdown('<div class="badge-green">🌐 App is LIVE</div>', unsafe_allow_html=True)
        st.caption("Backend: SQLite · Models: Local")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.user is None:
    auth_page()
else:
    render_sidebar()
    page = st.session_state.page

    if "🔬 Analyze" in page:
        analyze_page()
    elif "📂 History" in page:
        history_page()
    elif "🩺 Doctors" in page:
        doctors_page()
    elif "📁 Cases" in page:
        cases_page()
    elif "🔔 Notifications" in page:
        notifications_page()
    elif "👤 Profile" in page:
        profile_page()
    else:
        analyze_page()
