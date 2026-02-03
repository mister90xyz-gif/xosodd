#!/usr/bin/env python3
"""
Database initialization script
Run this before starting the bot for the first time
"""

from database import Database
from config import ADMIN_USER_ID

def main():
    print("Initializing database...")
    
    db = Database()
    
    print("✅ Database initialized successfully!")
    print(f"📋 Tables created: users, downloads, access_requests")
    
    if ADMIN_USER_ID:
        print(f"👑 Admin user ID: {ADMIN_USER_ID}")
        print("✅ Admin user added to database")
    else:
        print("⚠️  Warning: ADMIN_USER_ID not set in .env file")
    
    print("\n🎉 Setup complete! You can now start the bot.")
    
    db.close()

if __name__ == '__main__':
    main()
