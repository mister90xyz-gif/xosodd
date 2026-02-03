from database import Database

class UserManager:
    def __init__(self, db: Database):
        self.db = db
    
    def request_access(self, user_id, username, first_name, message=""):
        """User requests access to the bot"""
        # Check if user already exists
        user = self.db.get_user(user_id)
        
        if user:
            status = user[3]
            if status == 'approved' or status == 'admin':
                return {
                    'success': False,
                    'message': 'You are already authorized! You can use the bot.'
                }
            elif status == 'pending':
                return {
                    'success': False,
                    'message': 'Your request is already pending. Please wait for admin approval.'
                }
        else:
            # Add user with pending status
            self.db.add_user(user_id, username, first_name, status='pending')
        
        # Create access request
        success = self.db.create_access_request(user_id, username, first_name, message)
        
        if success:
            return {
                'success': True,
                'message': 'Your access request has been sent! An admin will review it shortly.'
            }
        else:
            return {
                'success': False,
                'message': 'Error sending request. Please try again.'
            }
    
    def approve_request(self, request_id):
        """Admin approves an access request"""
        request = self.db.get_request(request_id)
        
        if not request:
            return {
                'success': False,
                'message': 'Request not found.'
            }
        
        user_id = request[1]  # user_id column
        
        # Update user status to approved
        self.db.update_user_status(user_id, 'approved')
        
        # Update request status
        self.db.update_request_status(request_id, 'approved')
        
        return {
            'success': True,
            'user_id': user_id,
            'message': f'User {user_id} has been approved.'
        }
    
    def reject_request(self, request_id):
        """Admin rejects an access request"""
        request = self.db.get_request(request_id)
        
        if not request:
            return {
                'success': False,
                'message': 'Request not found.'
            }
        
        user_id = request[1]  # user_id column
        
        # Update user status to rejected
        self.db.update_user_status(user_id, 'rejected')
        
        # Update request status
        self.db.update_request_status(request_id, 'rejected')
        
        return {
            'success': True,
            'user_id': user_id,
            'message': f'User {user_id} has been rejected.'
        }
    
    def add_user_directly(self, user_id):
        """Admin adds a user directly without request"""
        user = self.db.get_user(user_id)
        
        if user:
            # Update to approved if exists
            self.db.update_user_status(user_id, 'approved')
            return {
                'success': True,
                'message': f'User {user_id} added/approved successfully.'
            }
        else:
            # Add new user as approved
            self.db.add_user(user_id, 'Unknown', 'Unknown', status='approved')
            return {
                'success': True,
                'message': f'User {user_id} added and approved.'
            }
    
    def remove_user(self, user_id):
        """Admin removes a user"""
        user = self.db.get_user(user_id)
        
        if not user:
            return {
                'success': False,
                'message': f'User {user_id} not found.'
            }
        
        if self.db.is_admin(user_id):
            return {
                'success': False,
                'message': 'Cannot remove admin user.'
            }
        
        self.db.remove_user(user_id)
        
        return {
            'success': True,
            'message': f'User {user_id} has been removed.'
        }
    
    def get_all_users_formatted(self):
        """Get formatted list of all users"""
        users = self.db.get_all_users()
        
        if not users:
            return "No users found."
        
        message = "📋 <b>All Users List:</b>\n\n"
        
        for user in users:
            user_id, username, first_name, status, created_at, _ = user
            status_emoji = {
                'admin': '👑',
                'approved': '✅',
                'pending': '⏳',
                'rejected': '❌'
            }.get(status, '❓')
            
            message += f"{status_emoji} <b>ID:</b> {user_id}\n"
            message += f"   <b>Name:</b> {first_name or 'Unknown'}\n"
            message += f"   <b>Username:</b> @{username or 'N/A'}\n"
            message += f"   <b>Status:</b> {status}\n\n"
        
        return message
    
    def get_pending_requests_formatted(self):
        """Get formatted list of pending requests and users"""
        requests = self.db.get_pending_requests()
        pending_users = self.db.get_pending_users()
        
        if not requests and not pending_users:
            return "No pending requests."
        
        message = "⏳ <b>Pending Access Requests:</b>\n\n"
        
        # 1. Show formal requests
        if requests:
            for req in requests:
                req_id, user_id, username, first_name, msg, status, created_at, _ = req
                
                message += f"🆔 <b>Request #{req_id}</b>\n"
                message += f"   <b>User ID:</b> {user_id}\n"
                message += f"   <b>Name:</b> {first_name or 'Unknown'}\n"
                message += f"   <b>Username:</b> @{username or 'N/A'}\n"
                if msg:
                    message += f"   <b>Message:</b> {msg}\n"
                message += f"   <b>Date:</b> {created_at}\n"
                # Use standard format for request approval
                message += f"\n   /approve_{req_id} | /reject_{req_id}\n\n"

        # 2. Show implicit requests (pending users without formal request)
        # Filter out users who already have a formal request shown above to avoid duplicates
        request_user_ids = [r[1] for r in requests]
        
        distinct_pending_users = [u for u in pending_users if u[0] not in request_user_ids]
        
        if distinct_pending_users:
            if requests:
                message += "---------\n"
                
            for user in distinct_pending_users:
                user_id, username, first_name, status, created_at, _ = user
                
                message += f"👤 <b>New User (No Request Message)</b>\n"
                message += f"   <b>User ID:</b> {user_id}\n"
                message += f"   <b>Name:</b> {first_name or 'Unknown'}\n"
                message += f"   <b>Username:</b> @{username or 'N/A'}\n"
                message += f"   <b>Date:</b> {created_at}\n"
                # Use special format for user direct approval
                message += f"\n   /approveuser_{user_id} | /rejectuser_{user_id}\n\n"
        
        return message
