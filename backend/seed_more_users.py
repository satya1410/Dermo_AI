from app.database import SessionLocal, engine
from app import db_models
from app.auth import get_password_hash
from sqlalchemy.exc import IntegrityError

def seed_users():
    db = SessionLocal()
    
    doctors = [
        {"email": "dr.rajesh@hospital.com", "specialty": "Cardiologist", "achievement": "MD, DM (Cardiology), 15+ Yrs Exp"},
        {"email": "dr.anita.sharma@hospital.com", "specialty": "Dermatologist", "achievement": "MD (Dermatology), Gold Medalist"},
        {"email": "dr.vikram@hospital.com", "specialty": "Neurologist", "achievement": "DM (Neurology), Ex-AIIMS"},
        {"email": "dr.priya@hospital.com", "specialty": "Pediatrician", "achievement": "MD (Pediatrics), Child Specialist"},
        {"email": "dr.amit@hospital.com", "specialty": "Orthopedic", "achievement": "MS (Ortho), Joint Replacement Surgeon"},
        {"email": "dr.sneha@hospital.com", "specialty": "Gynecologist", "achievement": "MD (OBG), Infertility Specialist"},
        {"email": "dr.manoj@hospital.com", "specialty": "General Physician", "achievement": "MD (Internal Medicine)"},
        {"email": "dr.kavita@hospital.com", "specialty": "Ophthalmologist", "achievement": "MS (Ophthalmology), Lasik Expert"},
        {"email": "dr.arjun@hospital.com", "specialty": "Psychiatrist", "achievement": "MD (Psychiatry), Mental Health Expert"},
        {"email": "dr.meera@hospital.com", "specialty": "Endocrinologist", "achievement": "DM (Endocrinology), Diabetes Specialist"}
    ]

    patients = [
        {"email": "rahul@gmail.com"},
        {"email": "anjali@gmail.com"},
        {"email": "rohan@gmail.com"},
        {"email": "sanya@gmail.com"},
        {"email": "karthik@gmail.com"}
    ]

    default_password = "password123"
    hashed_pw = get_password_hash(default_password) # Hash once, reuse (salt is same but fine for seeding)

    print("--- Seeding Doctors ---")
    for doc in doctors:
        # Re-hashing inside loop is safer practice even if slower, though passlib handles salts
        pw_hash = get_password_hash(default_password) 
        new_user = db_models.User(
            email=doc["email"],
            hashed_password=pw_hash,
            role="doctor",
            specialty=doc["specialty"],
            achievement=doc["achievement"]
        )
        try:
            db.add(new_user)
            db.commit()
            print(f"Added Doctor: {doc['email']}")
        except IntegrityError:
            db.rollback()
            print(f"Skipped (Exists): {doc['email']}")
        except Exception as e:
            db.rollback()
            print(f"Error {doc['email']}: {e}")

    print("\n--- Seeding Patients ---")
    for pat in patients:
        pw_hash = get_password_hash(default_password)
        new_user = db_models.User(
            email=pat["email"],
            hashed_password=pw_hash,
            role="patient"
        )
        try:
            db.add(new_user)
            db.commit()
            print(f"Added Patient: {pat['email']}")
        except IntegrityError:
            db.rollback()
            print(f"Skipped (Exists): {pat['email']}")
        except Exception as e:
            db.rollback()
            print(f"Error {pat['email']}: {e}")

    db.close()
    print("\n--- Seeding Complete ---")

if __name__ == "__main__":
    db_models.Base.metadata.create_all(bind=engine)
    seed_users()
