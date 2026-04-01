#!/usr/bin/env python3
"""
Script to display login information from doctors and patients database
"""
from app.database import SessionLocal, engine
from app import db_models
from tabulate import tabulate

# Create all tables if they don't exist
db_models.Base.metadata.create_all(bind=engine)

def display_users():
    db = SessionLocal()
    
    try:
        # Get all users
        all_users = db.query(db_models.User).all()
        
        print("\n" + "="*80)
        print("DATABASE USER INFORMATION")
        print("="*80 + "\n")
        
        if not all_users:
            print("No users found in database.\n")
            return
        
        # Separate doctors and patients
        doctors = [u for u in all_users if u.role == "doctor"]
        patients = [u for u in all_users if u.role == "patient"]
        
        # Display Doctors
        print(f"👨‍⚕️  DOCTORS ({len(doctors)} total)\n")
        if doctors:
            doctor_data = []
            for doc in doctors:
                doctor_data.append([
                    doc.id,
                    doc.email,
                    doc.specialty or "N/A",
                    doc.achievement or "N/A",
                    doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else "N/A"
                ])
            print(tabulate(doctor_data, 
                          headers=["ID", "Email", "Specialty", "Achievement", "Created At"],
                          tablefmt="grid"))
        else:
            print("No doctors found in database.\n")
        
        # Display Patients
        print(f"\n👤  PATIENTS ({len(patients)} total)\n")
        if patients:
            patient_data = []
            for pat in patients:
                patient_data.append([
                    pat.id,
                    pat.email,
                    pat.created_at.strftime("%Y-%m-%d %H:%M") if pat.created_at else "N/A"
                ])
            print(tabulate(patient_data,
                          headers=["ID", "Email", "Created At"],
                          tablefmt="grid"))
        else:
            print("No patients found in database.\n")
        
        print("\n" + "="*80)
        print(f"TOTAL USERS: {len(all_users)} (Doctors: {len(doctors)}, Patients: {len(patients)})")
        print("="*80 + "\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    display_users()
