from app.database import SessionLocal
from app import db_models

def verify_doctors():
    db = SessionLocal()
    doctors = db.query(db_models.User).filter(db_models.User.role == "doctor").all()
    
    print(f"Found {len(doctors)} doctors in the database:")
    for doc in doctors:
        print(f"- {doc.email} ({doc.specialty})")
    
    db.close()

if __name__ == "__main__":
    verify_doctors()
