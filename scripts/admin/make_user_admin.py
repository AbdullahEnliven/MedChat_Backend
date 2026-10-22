"""
Make User Admin Script
Run this to grant admin privileges to a user
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.user import User

def make_admin(email: str):
    """Make a user an admin by email"""
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Find user
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User not found: {email}")
            print("\nAvailable users:")
            all_users = db.query(User).all()
            for u in all_users:
                admin_status = "✓ ADMIN" if u.is_admin else "  USER"
                print(f"  [{admin_status}] {u.email} - {u.full_name}")
            return False
        
        if user.is_admin:
            print(f"✅ User {email} is already an admin!")
            return True
        
        # Make admin
        user.is_admin = True
        user.is_verified = True  # Also verify the account
        user.is_active = True    # Make sure active
        
        db.commit()
        
        print(f"✅ SUCCESS! {email} is now an admin!")
        print(f"   Name: {user.full_name}")
        print(f"   Status: Admin ✓ | Verified ✓ | Active ✓")
        print(f"\nYou can now access the admin panel!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("          Make User Admin Script")
    print("=" * 60)
    
    # Target email
    admin_email = "floydcooper57921@gmail.com"
    
    print(f"\nMaking admin: {admin_email}")
    print("-" * 60)
    
    success = make_admin(admin_email)
    
    print("=" * 60)
    
    if success:
        print("\n🎉 Admin setup complete!")
        print("   You can now:")
        print("   1. Login to your account")
        print("   2. Access admin panel")
        print("   3. View user statistics")
        print("   4. Manage users")
    
    sys.exit(0 if success else 1)
