"""
Simple Admin User Creation Script
Usage: python create_admin_simple.py
"""

from getpass import getpass
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import User
from app.utils.auth import hash_password, validate_password_strength


def create_admin():
    """Interactive script to create an admin user"""
    
    print("=" * 60)
    print("Med-Chat Admin User Creation")
    print("=" * 60)
    print()
    
    # Get user input
    email = input("Enter admin email: ").strip()
    if not email:
        print("Error: Email cannot be empty")
        return
    
    full_name = input("Enter admin full name: ").strip()
    if not full_name:
        print("Error: Full name cannot be empty")
        return
    
    password = getpass("Enter admin password: ").strip()
    if not password:
        print("Error: Password cannot be empty")
        return
    
    # Validate password strength
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        print(f"Error: Password validation failed: {message}")
        return
    
    confirm_password = getpass("Confirm password: ").strip()
    if password != confirm_password:
        print("Error: Passwords do not match")
        return
    
    print()
    print("Creating admin user...")
    print(f"  Email: {email}")
    print(f"  Name: {full_name}")
    print()
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"User with email '{email}' already exists")
            
            # Ask if user wants to make existing user an admin
            make_admin = input("Make this user an admin? (yes/no): ").strip().lower()
            if make_admin == 'yes':
                existing_user.is_admin = True
                existing_user.is_verified = True
                existing_user.is_active = True
                db.commit()
                print(f"SUCCESS: User '{email}' is now an admin")
            return
        
        # Create new admin user
        hashed_password = hash_password(password)
        
        admin_user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            is_admin=True,
            is_verified=True,  # Auto-verify admin
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print("SUCCESS: Admin user created successfully!")
        print()
        print("Admin Details:")
        print(f"  ID: {admin_user.id}")
        print(f"  Email: {admin_user.email}")
        print(f"  Name: {admin_user.full_name}")
        print(f"  Admin: {admin_user.is_admin}")
        print(f"  Verified: {admin_user.is_verified}")
        print(f"  Active: {admin_user.is_active}")
        print()
        print("You can now login via the API:")
        print(f"  POST http://localhost:8000/api/v1/auth/login")
        print(f"  Body: {{'email': '{email}', 'password': 'your_password'}}")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating admin user: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    try:
        create_admin()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
