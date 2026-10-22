"""
Migration Script: Add Gender and Birthday Fields to Users Table
Run this script to add the new fields to existing database
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.core.database import engine, SessionLocal

def add_user_profile_fields():
    """Add gender, date_of_birth, and age columns to users table"""
    
    print("Starting migration: Adding user profile fields...")
    
    try:
        with engine.connect() as connection:
            # Check if columns already exist
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' 
                AND column_name IN ('gender', 'date_of_birth', 'age')
            """)
            
            result = connection.execute(check_query)
            existing_columns = [row[0] for row in result]
            
            if 'gender' in existing_columns and 'date_of_birth' in existing_columns and 'age' in existing_columns:
                print("✓ Columns already exist. No migration needed.")
                return
            
            # Add gender column if it doesn't exist
            if 'gender' not in existing_columns:
                print("  Adding 'gender' column...")
                connection.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN gender VARCHAR(20)
                """))
                connection.commit()
                print("  ✓ 'gender' column added")
            
            # Add date_of_birth column if it doesn't exist
            if 'date_of_birth' not in existing_columns:
                print("  Adding 'date_of_birth' column...")
                connection.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN date_of_birth DATE
                """))
                connection.commit()
                print("  ✓ 'date_of_birth' column added")
            
            # Add age column if it doesn't exist
            if 'age' not in existing_columns:
                print("  Adding 'age' column...")
                connection.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN age INTEGER
                """))
                connection.commit()
                print("  ✓ 'age' column added")
            
            print("\n✅ Migration completed successfully!")
            print("\nNew fields added to users table:")
            print("  - gender (VARCHAR(20), nullable)")
            print("  - date_of_birth (DATE, nullable)")
            print("  - age (INTEGER, nullable)")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nNote: If database doesn't exist yet, this is normal.")
        print("The fields will be created when you initialize the database.")
        raise


if __name__ == "__main__":
    add_user_profile_fields()
