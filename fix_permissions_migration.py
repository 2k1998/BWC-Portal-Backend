#!/usr/bin/env python3
"""
Migration to fix permissions column data type inconsistency.
This script converts any list-type permissions to empty dictionaries.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine
from models import User
from sqlalchemy import text
import json

def migrate_permissions():
    """Fix permissions column data type inconsistency"""
    db = SessionLocal()
    try:
        print("Starting permissions migration...")
        
        # Get all users with permissions
        users = db.query(User).all()
        
        updated_count = 0
        for user in users:
            if user.permissions is not None:
                # Convert list to empty dict if needed
                if isinstance(user.permissions, list):
                    print(f"Converting permissions for user {user.id} ({user.email}) from list to dict")
                    user.permissions = {}
                    updated_count += 1
                # Handle string permissions (shouldn't happen but just in case)
                elif isinstance(user.permissions, str):
                    try:
                        parsed = json.loads(user.permissions)
                        if isinstance(parsed, list):
                            print(f"Converting string list permissions for user {user.id} ({user.email}) to dict")
                            user.permissions = {}
                            updated_count += 1
                        elif isinstance(parsed, dict):
                            # Already a dict, no change needed
                            pass
                        else:
                            print(f"Unknown permissions type for user {user.id} ({user.email}), setting to empty dict")
                            user.permissions = {}
                            updated_count += 1
                    except json.JSONDecodeError:
                        print(f"Invalid JSON permissions for user {user.id} ({user.email}), setting to empty dict")
                        user.permissions = {}
                        updated_count += 1
        
        if updated_count > 0:
            db.commit()
            print(f"Successfully updated permissions for {updated_count} users")
        else:
            print("No users needed permissions migration")
            
        print("Permissions migration completed successfully")
        
    except Exception as e:
        print(f"Error during permissions migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_permissions()
