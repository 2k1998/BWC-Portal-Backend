import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# New DB_URL for PostgreSQL
# User: hepdeska_user (the user you created in Step 2.2)
# Password: the password you set in Step 2.2 (K05051998kL.A.)
# Database: hepdeska_db
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://hepdeska_user:K05051998kL.A.@localhost:5432/hepdeska_db"
)

# Simplified engine - connect_args={"check_same_thread": False} is not needed for PostgreSQL
engine = create_engine(DB_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
