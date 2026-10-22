"""
Database migration script to add profile_photo_url column to users table
Run this script to update existing databases
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def add_profile_photo_column():
    """Add profile_photo_url column to users table if it doesn't exist"""
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as connection:
        try:
            # Check if column already exists
            result = connection.execute(text(
                "SELECT COUNT(*) FROM pragma_table_info('users') WHERE name='profile_photo_url'"
            ))
            
            column_exists = result.scalar() > 0
            
            if column_exists:
                print("✅ Column 'profile_photo_url' already exists in users table")
                return
            
            # Add the column
            print("Adding 'profile_photo_url' column to users table...")
            connection.execute(text(
                "ALTER TABLE users ADD COLUMN profile_photo_url VARCHAR(500)"
            ))
            connection.commit()
            
            print("✅ Successfully added 'profile_photo_url' column to users table")
            
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            connection.rollback()
            raise

if __name__ == "__main__":
    print("Starting database migration...")
    add_profile_photo_column()
    print("Migration completed!")
