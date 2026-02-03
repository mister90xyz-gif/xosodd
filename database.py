import sqlite3
from datetime import datetime
from config import DATABASE_PATH, ADMIN_USER_ID

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.ensure_admin_exists()
    
    def create_tables(self):
        """Create all necessary database tables"""
        # Users table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Download history table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                title TEXT,
                file_type TEXT,
                file_size INTEGER,
                download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Access requests table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        self.conn.commit()
    
    def ensure_admin_exists(self):
        """Ensure admin user exists in database"""
        if ADMIN_USER_ID:
            user = self.get_user(ADMIN_USER_ID)
            if not user:
                self.add_user(ADMIN_USER_ID, "Admin", "Admin", status="admin")
            elif user[3] != 'admin':  # status column
                self.update_user_status(ADMIN_USER_ID, "admin")
    
    def add_user(self, user_id, username, first_name, status='pending'):
        """Add a new user to the database"""
        try:
            self.cursor.execute('''
                INSERT INTO users (user_id, username, first_name, status)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, status))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_user(self, user_id):
        """Get user information"""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def update_user_status(self, user_id, status):
        """Update user status"""
        self.cursor.execute('''
            UPDATE users 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (status, user_id))
        self.conn.commit()
    
    def remove_user(self, user_id):
        """Remove a user from database"""
        self.cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def get_all_users(self):
        """Get all users"""
        self.cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
        return self.cursor.fetchall()
    
    def is_user_authorized(self, user_id):
        """Check if user is authorized (admin or approved)"""
        user = self.get_user(user_id)
        if not user:
            return False
        status = user[3]  # status column
        return status in ['admin', 'approved']
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        user = self.get_user(user_id)
        if not user:
            return False
        return user[3] == 'admin'
    
    # Access Request Methods
    def create_access_request(self, user_id, username, first_name, message):
        """Create a new access request"""
        try:
            self.cursor.execute('''
                INSERT INTO access_requests (user_id, username, first_name, message)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, message))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error creating access request: {e}")
            return False
    
    def get_pending_requests(self):
        """Get all pending access requests"""
        self.cursor.execute('''
            SELECT * FROM access_requests 
            WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        return self.cursor.fetchall()
    
    def get_pending_users(self):
        """Get all users with pending status"""
        self.cursor.execute("SELECT * FROM users WHERE status = 'pending'")
        return self.cursor.fetchall()
    
    def update_request_status(self, request_id, status):
        """Update access request status"""
        self.cursor.execute('''
            UPDATE access_requests 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, request_id))
        self.conn.commit()
    
    def get_request_by_id(self, request_id):
        """Get access request by ID"""
        self.cursor.execute('SELECT * FROM access_requests WHERE id = ?', (request_id,))
        return self.cursor.fetchone()
    
    # Download History Methods
    def add_download(self, user_id, url, title, file_type, file_size):
        """Add download to history"""
        self.cursor.execute('''
            INSERT INTO downloads (user_id, url, title, file_type, file_size)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, url, title, file_type, file_size))
        self.conn.commit()
    
    def get_user_downloads(self, user_id):
        """Get download history for a user"""
        self.cursor.execute('''
            SELECT * FROM downloads 
            WHERE user_id = ?
            ORDER BY download_date DESC
        ''', (user_id,))
        return self.cursor.fetchall()
    
    def close(self):
        """Close database connection"""
        self.conn.close()
