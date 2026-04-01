from app.database import SessionLocal, engine
from app import db_models
from app.auth import get_password_hash
from sqlalchemy.exc import IntegrityError

def add_doctors():
    db = SessionLocal()
    
    doctors = [
        {
            "email": "alice@hospital.com",
            "password": "password123",
            "specialty": "Dermatologist",
            "achievement": "PhD, 15 years experience, Board Certified"
        },
        {
            "email": "bob@hospital.com",
            "password": "password123",
            "specialty": "Oncologist",
            "achievement": "MD, Head of Oncology Dept"
        },
        {
            "email": "carol@hospital.com",
            "password": "password123",
            "specialty": "General Practitioner",
            "achievement": "MBBS, Family Medicine Specialist"
        }
    ]

    print("--- Adding Doctors ---")
    
    for doc in doctors:
        hashed_pw = get_password_hash(doc["password"])
        new_user = db_models.User(
            email=doc["email"],
            hashed_password=hashed_pw,
            role="doctor",
            specialty=doc["specialty"],
            achievement=doc["achievement"]
        )
        
        try:
            db.add(new_user)
            db.commit()
            print(f"Successfully added Doctor: {doc['email']} | Password: {doc['password']}")
        except IntegrityError:
            db.rollback()
            print(f"Doctor {doc['email']} already exists. Skipping.")
        except Exception as e:
            db.rollback()
            print(f"Error adding {doc['email']}: {e}")

    db.close()
    print("--- Done ---")

if __name__ == "__main__":
    # Ensure tables exist (redundant if app runs typically, but good for standalone script)
    db_models.Base.metadata.create_all(bind=engine)
    add_doctors()
