from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="patient") # 'doctor' or 'patient'
    
    # Doctor Specific Fields
    specialty = Column(String, nullable=True)     # e.g., "Dermatologist"
    achievement = Column(String, nullable=True)   # e.g., "PhD, 10 years experience"
    
    created_at = Column(DateTime, default=datetime.utcnow)

    predictions = relationship("Prediction", back_populates="owner", foreign_keys="Prediction.user_id")
    notifcations = relationship("Notification", back_populates="user")

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Assigned doctor
    
    status = Column(String, default="pending") # 'pending', 'accepted', 'rejected'
    
    image_path = Column(String) 
    diagnosis = Column(String)
    confidence = Column(Float)
    report_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="predictions", foreign_keys=[user_id])
    doctor = relationship("User", foreign_keys=[doctor_id])

class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"))
    prediction_id = Column(Integer, ForeignKey("predictions.id"))
    
    scheduled_at = Column(DateTime)
    status = Column(String, default="scheduled") # 'scheduled', 'completed', 'cancelled'
    meeting_link = Column(String, nullable=True)
    
    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message = Column(Text)
    is_read = Column(Integer, default=0) # 0 for false, 1 for true
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="notifcations")
