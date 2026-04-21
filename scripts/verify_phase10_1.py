import sys
import os
from uuid import uuid4

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.utils.notification_service import create_notification
from app.models.user import User
from app.models.notification import Notification
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

def verify_constraints():
    db = SessionLocal()
    try:
        print("\n--- Phase 10.1 Verification: Strict Constraints ---\n")
        
        # Get a valid user for FKs
        user = db.query(User).first()
        if not user:
            print("SKIPPING: No users found in DB to test with.")
            return

        # --- Test 1: Service Level Validation ---
        print("1. Testing Service Layer Validation (Invalid Type)...")
        try:
            create_notification(
                db=db,
                recipient_ids=[user.id],
                actor_id=None,
                entity_type="Task",
                entity_id=str(uuid4()),
                title="Test",
                message="Test",
                link="/test",
                notification_type="INVALID_TYPE" # <--- Should fail
            )
            print("FAILURE: Service allowed invalid notification_type!")
        except ValueError as e:
            print(f"SUCCESS: Service blocked invalid type: {e}")
        except Exception as e:
            print(f"FAILURE: Unexpected error: {e}")

        # --- Test 2: DB Level Check Constraint (Notification Type) ---
        print("\n2. Testing DB CHECK Constraint (Invalid Type via SQL)...")
        try:
            # Attempt raw SQL insert to bypass service
            sql = text("""
                INSERT INTO notifications (id, recipient_user_id, entity_type, entity_id, title, message, link, read_status, notification_type, created_at)
                VALUES (:id, :uid, 'Task', :eid, 'Raw SQL', 'Msg', '/link', 'Unread', 'INVALID_DB', NOW())
            """)
            db.execute(sql, {"id": uuid4(), "uid": user.id, "eid": uuid4()})
            db.commit()
            print("FAILURE: DB allowed invalid notification_type!")
        except IntegrityError as e:
            print(f"SUCCESS: DB blocked invalid type: {e.orig}")
            db.rollback()
        except Exception as e:
            print(f"FAILURE: Unexpected error: {type(e)} - {e}")
            db.rollback()

        # --- Test 3: DB Level Check Constraint (Read Status) ---
        print("\n3. Testing DB CHECK Constraint (Invalid Read Status)...")
        try:
             # Attempt raw SQL insert
            sql = text("""
                INSERT INTO notifications (id, recipient_user_id, entity_type, entity_id, title, message, link, read_status, notification_type, created_at)
                VALUES (:id, :uid, 'Task', :eid, 'Raw SQL', 'Msg', '/link', 'INVALID_STATUS', 'ASSIGNMENT', NOW())
            """)
            db.execute(sql, {"id": uuid4(), "uid": user.id, "eid": uuid4()})
            db.commit()
            print("FAILURE: DB allowed invalid read_status!")
        except IntegrityError as e:
            print(f"SUCCESS: DB blocked invalid read_status: {e.orig}")
            db.rollback()
        except Exception as e:
            print(f"FAILURE: Unexpected error: {type(e)} - {e}")
            db.rollback()

        # --- Test 4: Valid Insert ---
        print("\n4. Testing Valid Insert...")
        try:
            create_notification(
                db=db,
                recipient_ids=[user.id],
                actor_id=None,
                entity_type="Task",
                entity_id=str(uuid4()),
                title="Valid",
                message="Valid",
                link="/valid",
                notification_type="ASSIGNMENT" # Valid
            )
            # Service does not commit, so we commit here to check DB constraints trigger happy path
            db.commit()
            print("SUCCESS: Valid notification inserted.")
        except Exception as e:
            print(f"FAILURE: Valid insert failed: {e}")
            db.rollback()

    finally:
        db.close()

if __name__ == "__main__":
    verify_constraints()
