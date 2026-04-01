
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import torch
import torch.nn.functional as F
from PIL import Image
import io
import base64
import numpy as np
import cv2
import os
from typing import List

# Import our modules (using ml_model now)
from app.ml_model import load_model, CLASSES, Config
from app.gradcam import GradCAM, overlay_cam
from app.report import generate_report
from app.wound_model import load_wound_model, predict_wound
from app import database, db_models, auth

# Create DB Tables
db_models.Base.metadata.create_all(bind=database.engine)

router = APIRouter()

# Global Model Load
model, device = load_model()
wound_model, wound_device, wound_num_classes = load_wound_model()

# --- Pydantic Schemas for Auth ---
class UserRegister(BaseModel):
    email: str
    password: str
    role: str = "patient" # 'patient' or 'doctor'
    specialty: str = None
    achievement: str = None

class Token(BaseModel):
    access_token: str
    token_type: str

class PredictionOut(BaseModel):
    id: int
    diagnosis: str
    confidence: float
    created_at: str
    
    class Config:
        orm_mode = True

# --- TRANSFORM HELPERS ---
def transform_image(image_bytes):
    from torchvision import transforms
    my_transforms = transforms.Compose([
        transforms.Resize((Config.IMAGE_SIZE, Config.IMAGE_SIZE)), 
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return my_transforms(image).unsqueeze(0).to(device), image 

# --- AUTH ENDPOINTS ---

@router.post("/auth/register")
def register(user: UserRegister, db: Session = Depends(database.get_db)):
    # Check if exists
    db_user = db.query(db_models.User).filter(db_models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pw = auth.get_password_hash(user.password)
    new_user = db_models.User(
        email=user.email, 
        hashed_password=hashed_pw, 
        role=user.role,
        specialty=user.specialty,
        achievement=user.achievement
    )
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@router.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    # Note: OAuth2PasswordRequestForm expects 'username' field, we map email to it
    user = db.query(db_models.User).filter(db_models.User.email == form_data.username).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    if not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = auth.create_access_token(data={"sub": user.email, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me")
def read_users_me(current_user: db_models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at
    }

@router.get("/history")
def get_history(current_user: db_models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    if current_user.role == "doctor":
        # Doctors see cases assigned to them or accepted by them
        preds = db.query(db_models.Prediction).filter(
            (db_models.Prediction.doctor_id == current_user.id) | (db_models.Prediction.status == "pending")
        ).order_by(db_models.Prediction.created_at.desc()).all()
    else:
        # Patients see their own history
        preds = db.query(db_models.Prediction).filter(db_models.Prediction.user_id == current_user.id).order_by(db_models.Prediction.created_at.desc()).all()
    
    results = []
    for p in preds:
        results.append({
            "id": p.id,
            "diagnosis": p.diagnosis,
            "confidence": p.confidence,
            "status": p.status,
            "date": p.created_at.isoformat(),
            "report_preview": p.report_text[:100] + "..." if p.report_text else ""
        })
    return results

@router.get("/history/{id}")
def get_history_item(id: int, current_user: db_models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    pred = db.query(db_models.Prediction).filter(db_models.Prediction.id == id, db_models.Prediction.user_id == current_user.id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Try to load the associated heatmap if it exists
    heatmap_b64 = None
    if pred.image_path and os.path.exists(pred.image_path):
        # Infer heatmap path from original path
        # Format was: {unique_id}.jpg -> {unique_id}_heatmap.png
        dir_name = os.path.dirname(pred.image_path)
        base_name = os.path.basename(pred.image_path)
        name_part = os.path.splitext(base_name)[0]
        
        heatmap_path = os.path.join(dir_name, f"{name_part}_heatmap.png")
        
        if os.path.exists(heatmap_path):
            with open(heatmap_path, "rb") as f:
                heatmap_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    return {
        "id": pred.id,
        "diagnosis": pred.diagnosis,
        "report_text": pred.report_text,
        "date": pred.created_at,
        "heatmap_base64": heatmap_b64 # Helper for frontend
    }

# --- CASE MANAGEMENT ---

@router.get("/cases/pending")
def get_pending_cases(current_user: db_models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    cases = db.query(db_models.Prediction).filter(db_models.Prediction.status == "pending").all()
    return cases

@router.post("/cases/{case_id}/accept")
def accept_case(case_id: int, current_user: db_models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    if current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    case = db.query(db_models.Prediction).filter(db_models.Prediction.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case.status = "accepted"
    case.doctor_id = current_user.id
    
    # Send Notification to Patient
    notification = db_models.Notification(
        user_id=case.user_id,
        message=f"Doctor {current_user.email} has accepted your case."
    )
    db.add(notification)
    db.commit()
    return {"message": "Case accepted"}

@router.get("/notifications")
def get_notifications(current_user: db_models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    notifs = db.query(db_models.Notification).filter(db_models.Notification.user_id == current_user.id).all()
    return notifs

@router.get("/doctors")
def list_doctors(db: Session = Depends(database.get_db)):
    doctors = db.query(db_models.User).filter(db_models.User.role == "doctor").all()
    return [{"id": d.id, "email": d.email, "specialty": d.specialty, "achievement": d.achievement} for d in doctors]

# --- PREDICTION ENDPOINT ---

@router.post("/predict")
async def predict_lesion(
    file: UploadFile = File(...), 
    api_key: str = Form(default=None),
    token: str = Form(default=None), # Optional auth token passed in form
    db: Session = Depends(database.get_db)
):
    user = None
    if token and token != "null" and token != "":
        try:
            user = await auth.get_current_user(token, db)
        except:
            pass # Continue as guest if token invalid

    try:
        # Save Original File
        UPLOAD_DIR = "uploads"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        image_bytes = await file.read()
        
        import uuid
        import time
        unique_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        filename = f"{unique_id}.jpg"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Save bytes directly or via PIL
        with open(file_path, "wb") as f:
            f.write(image_bytes)

        tensor, original_pil = transform_image(image_bytes)

        # 1. WOUND GATE — check image before running skin lesion model
        wound_label = None
        try:
            is_wound, wound_label, wound_conf = predict_wound(wound_model, wound_device, wound_num_classes, image_bytes)
        except Exception as we:
            print(f"Wound gate error (skipping): {we}")
            is_wound = False

        if is_wound:
            print(f"🩹 Wound detected: {wound_label} ({wound_conf:.1f}%)")
            report_text = generate_report(wound_label, wound_conf, api_key, image_bytes=image_bytes, wound_label=wound_label)
            if user:
                new_pred = db_models.Prediction(
                    user_id=user.id,
                    image_path=file_path,
                    diagnosis=f"Wound: {wound_label}",
                    confidence=wound_conf,
                    report_text=report_text
                )
                db.add(new_pred)
                db.commit()
            return JSONResponse({
                "diagnosis": f"Wound: {wound_label}",
                "heatmap_base64": None,
                "report": report_text,
                "saved": True if user else False,
                "_confidence": wound_conf
            })

        # 2. Skin Lesion Prediction
        with torch.no_grad():
            outputs = model(tensor)
            probs = F.softmax(outputs, dim=1)
            confidence, predicted_idx = torch.max(probs, 1)
            
        class_idx = predicted_idx.item()
        
        if class_idx < len(CLASSES):
            class_name = CLASSES[class_idx]
        else:
            class_name = "Unknown"
            
        conf_score = confidence.item() * 100
        
        # 3. Grad-CAM
        target_layer = None
        
        try:
            # For MultiLayerHybridModel - use individual conv block, not Sequential wrapper
            # Select the last InvertedResidual block from EfficientNet
            if hasattr(model, 'local') and hasattr(model.local, 'blocks'):
                # local.blocks is a list/ModuleList - get last block, then last sub-block
                last_block = model.local.blocks[-1]
                # If it's a Sequential, get the last element
                if isinstance(last_block, torch.nn.Sequential) and len(last_block) > 0:
                    # Try to use the second-to-last block to ensure it has spatial dimensions
                    target_layer = last_block[-2] if len(last_block) >= 2 else last_block[-1]
                    print(f"DEBUG: Selected InvertedResidual from local.blocks[-1]: {type(target_layer)}")
                else:
                    target_layer = last_block
                    print(f"DEBUG: Selected entire block from local.blocks[-1]: {type(target_layer)}")
            
            # Fallback: try blocks directly
            if target_layer is None and hasattr(model, 'local') and hasattr(model.local, 'blocks'):
                # Try the second-to-last full block
                if len(model.local.blocks) >= 2:
                    target_layer = model.local.blocks[-2]
                    print(f"DEBUG: Using second-to-last block: {type(target_layer)}")
            
            # Fallback: try globalm
            if target_layer is None and hasattr(model, 'globalm'):
                if hasattr(model.globalm, 'stages_3'):
                    target_layer = model.globalm.stages_3
                    print(f"DEBUG: Selected from globalm.stages_3: {type(target_layer)}")
                elif hasattr(model.globalm, 'stages_2'):
                    target_layer = model.globalm.stages_2
                    print(f"DEBUG: Selected from globalm.stages_2: {type(target_layer)}")
        except Exception as e:
            print(f"Error selecting target layer: {e}")
            import traceback
            traceback.print_exc()
            target_layer = None
        
        if target_layer is None:
            print(f"WARNING: Could not find suitable target layer for Grad-CAM")
        
        img_base64 = None
        if target_layer:
            try:
                # NOTE: Keep model in eval mode to avoid BatchNorm issues with batch_size=1
                # But we need gradients enabled for backprop
                model.eval()
                
                # Enable gradient computation for this specific forward pass
                tensor_with_grad = tensor.clone().detach().requires_grad_(True)
                
                with GradCAM(model, target_layer) as grad_cam:
                    mask, _, _ = grad_cam(tensor_with_grad, class_idx)
                
                print(f"GradCAM mask - min: {mask.min()}, max: {mask.max()}, mean: {mask.mean()}")
                
                img_np = np.array(original_pil.resize((Config.IMAGE_SIZE, Config.IMAGE_SIZE)))
                img_np = img_np.astype(np.float32) / 255.0
                
                cam_result = overlay_cam(img_np, mask, alpha=0.6)
                
                cam_result = (cam_result * 255).astype(np.uint8)
                cam_result = cv2.cvtColor(cam_result, cv2.COLOR_RGB2BGR) 
                
                # Save Heatmap
                heatmap_filename = f"{unique_id}_heatmap.png"
                heatmap_path = os.path.join(UPLOAD_DIR, heatmap_filename)
                cv2.imwrite(heatmap_path, cam_result)
                
                _, buffer = cv2.imencode('.png', cam_result)
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                print(f"✓ Grad-CAM generated successfully")
            except Exception as e:
                print(f"GradCAM failed: {e}")
                import traceback
                traceback.print_exc()
 
        
        # 4. Image-grounded XAI Report via Gemini
        report_text = generate_report(class_name, conf_score, api_key, image_bytes=image_bytes)
        
        # 4. Save to DB if logged in
        if user:
            new_pred = db_models.Prediction(
                user_id=user.id,
                image_path=file_path,
                diagnosis=class_name,
                confidence=conf_score,
                report_text=report_text
            )
            db.add(new_pred)
            db.commit()
        
        return JSONResponse({
            "diagnosis": class_name,
            "heatmap_base64": img_base64,
            "report": report_text,
            "saved": True if user else False,
            # Internal use only - not displayed to user
            "_confidence": conf_score
        })
        
    except Exception as e:
        print(f"Error prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- APPOINTMENT ENDPOINTS ---

@router.get("/doctors/{doctor_id}/slots")
def get_doctor_slots(doctor_id: int, db: Session = Depends(database.get_db)):
    from datetime import datetime, timedelta
    
    # Generate next 10 days
    today = datetime.now().date()
    dates = [today + timedelta(days=i) for i in range(10)]
    
    # Simple fixed slots for now
    base_slots = ["10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM"]
    
    available_slots = []
    
    for d in dates:
        date_str = d.strftime("%Y-%m-%d") # ISO format
        day_name = d.strftime("%a") # Mon, Tue...
        
        day_slots = []
        for time_str in base_slots:
            status = "available"
            if time_str == "01:00 PM": # Mock busy/lunch slot
                status = "booked"
            
            day_slots.append({
                "time": time_str,
                "status": status
            })
            
        available_slots.append({
            "date": date_str,
            "day": day_name,
            "slots": day_slots
        })
        
    return available_slots

class AppointmentCreate(BaseModel):
    doctor_id: int
    date: str # YYYY-MM-DD
    time: str # 10:00 AM

@router.post("/appointments")
def create_appointment(
    appt: AppointmentCreate, 
    current_user: db_models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    from datetime import datetime
    
    # Parse date and time
    dt_str = f"{appt.date} {appt.time}"
    try:
        scheduled_at = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date/time format")
        
    new_appt = db_models.Appointment(
        patient_id=current_user.id,
        doctor_id=appt.doctor_id,
        scheduled_at=scheduled_at,
        status="scheduled"
    )
    db.add(new_appt)
    
    # Notify Doctor
    notif = db_models.Notification(
        user_id=appt.doctor_id,
        message=f"New appointment request from {current_user.email} on {appt.date} at {appt.time}.",
        is_read=0
    )
    db.add(notif)
    
    db.commit()
    
    return {"message": "Appointment scheduled successfully"}
