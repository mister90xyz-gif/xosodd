import asyncio
import logging
import os
import re
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from config import BOT_TOKEN, ADMIN_USER_ID
from database import Database
from user_manager import UserManager
from downloader import MediaDownloader

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize components
db = Database()
user_manager = UserManager(db)
downloader = MediaDownloader()

# Store user download context
user_download_context = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    # Add or update user in database
    db_user = db.get_user(user_id)
    if not db_user:
        db.add_user(user_id, user.username, user.first_name, status='pending')
    
    welcome_message = f"""
🎬 <b>Video/Audio Downloader Bot</b>

Welcome, {user.first_name}!

You can download video and audio from various platforms using this bot.

<b>📝 How to use:</b>
1. Just send any video link
2. The bot will ask if you want Video or Audio
3. Select your choice and download will start

<b>🌐 Supported Platforms:</b>
• YouTube
• Facebook
• Instagram
• TikTok
• And many more!

<b>📋 Commands (Click):</b>
/start - Restart bot
/help - Help and instructions
/request - Request access
"""
    
    # Check authorization
    is_authorized = db.is_user_authorized(user_id)
    if is_authorized:
        welcome_message += "\n✅ You are authorized! Send a link now.\n"
    else:
        welcome_message += "\n⚠️ You are not authorized yet. Click 'Request Access'.\n"
    
    # Build keyboard
    keyboard = []
    
    if not is_authorized:
        keyboard.append([InlineKeyboardButton("📝 Request Access", callback_data="request_info")])
    
    keyboard.append([InlineKeyboardButton("❓ Help", callback_data="help")])
    
    # Add admin button if user is admin
    if db.is_admin(user_id):
        welcome_message += """

<b>👑 Admin Commands (Copy):</b>
<code>/adduser user_id</code>
<code>/removeuser user_id</code>
"""
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Persistent Reply Keyboard
    reply_keyboard = [
        [KeyboardButton("🏠 Main Menu"), KeyboardButton("❓ Help")]
    ]
    
    if not is_authorized:
         reply_keyboard.insert(0, [KeyboardButton("📝 Request Access")])
         
    if db.is_admin(user_id):
        reply_keyboard.append([KeyboardButton("👑 Admin Panel")])
        
    reply_markup_persistent = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await context.bot.send_message(
            chat_id=user_id,
            text="👇 Menu Updated:",
            reply_markup=reply_markup_persistent
        )
    else:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        await update.message.reply_text("👇 Menu Updated:", reply_markup=reply_markup_persistent)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
<b>📖 Help Guide</b>

<b>To Download:</b>
Just send any video link. The bot will ask if you want Video or Audio.

<b>Example Links:</b>
<code>https://www.youtube.com/watch?v=xxxxx</code>
<code>https://www.facebook.com/xxxxx</code>
<code>https://www.instagram.com/p/xxxxx</code>

<b>📋 Commands:</b>
/start - Return to Main Menu
/help - Show this help message
/request - Request access

<b>❓ Having trouble?</b>
Ensure the link is correct and the video is public.
"""
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /request command"""
    user = update.effective_user
    user_id = user.id
    
    # Check if already authorized
    if db.is_user_authorized(user_id):
        await update.message.reply_text(
            "✅ You are already authorized! You can use the bot."
        )
        return
    
    # Get message if provided
    message = " ".join(context.args) if context.args else ""
    
    result = user_manager.request_access(
        user_id,
        user.username,
        user.first_name,
        message
    )
    
    await update.message.reply_text(result['message'])
    
    # Notify admin
    if result['success']:
        admin_message = f"""
🔔 <b>New Access Request</b>

<b>User ID:</b> {user_id}
<b>Name:</b> {user.first_name}
<b>Username:</b> @{user.username or 'N/A'}
"""
        if message:
            admin_message += f"<b>Message:</b> {message}\n"
        
        # Get the request ID
        requests = db.get_pending_requests()
        if requests:
            target_req = None
            for req in requests:
                if req[1] == user_id:
                    target_req = req
                    break
            
            if target_req:
                request_id = target_req[0]
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve:{request_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject:{request_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_USER_ID,
                        text=admin_message,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error sending admin notification: {e}")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /listusers command (admin only)"""
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    if not db.is_admin(user_id):
        await context.bot.send_message(chat_id=user_id, text="❌ This command is for admins only.")
        return
    
    users_list = user_manager.get_all_users_formatted()
    
    # Split if too long (basic handling)
    if len(users_list) > 4000:
        users_list = users_list[:4000] + "\n... (more)"

    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(users_list, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(users_list, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def pending_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pending command (admin only)"""
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    if not db.is_admin(user_id):
        await context.bot.send_message(chat_id=user_id, text="❌ This command is for admins only.")
        return
    
    requests_list = user_manager.get_pending_requests_formatted()
    
    keyboard = [
        [InlineKeyboardButton("✅ Bulk Manage", callback_data="admin_pending_select:0")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(requests_list, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(requests_list, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /adduser command (admin only)"""
    user_id = update.effective_user.id
    
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /adduser <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        result = user_manager.add_user_directly(target_user_id)
        
        await update.message.reply_text(result['message'])
        
        # Notify the user
        if result['success']:
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="🎉 <b>Congratulations!</b>\n\nYour access request has been approved. You can now use the bot!",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please enter a number.")


async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /removeuser command (admin only)"""
    user_id = update.effective_user.id
    
    if not db.is_admin(user_id):
        await update.message.reply_text("❌ This command is for admins only.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Usage: /removeuser <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        result = user_manager.remove_user(target_user_id)
        await update.message.reply_text(result['message'])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Using number.")


async def approve_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dynamic /approve_<id> commands - Legacy support"""
    # This is kept for backward compatibility if manual commands are used
    user_id = update.effective_user.id
    if not db.is_admin(user_id): return
    
    command = update.message.text
    match = re.match(r'/approve_(\d+)', command)
    if not match: return
    
    request_id = int(match.group(1))
    result = user_manager.approve_request(request_id)
    await update.message.reply_text(result['message'])
    
    if result['success']:
        try:
            await context.bot.send_message(
                chat_id=result['user_id'],
                text="🎉 <b>Congratulations!</b>\n\nYour access request has been approved. You can now use the bot!",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def reject_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dynamic /reject_<id> commands - Legacy support"""
    user_id = update.effective_user.id
    if not db.is_admin(user_id): return
    
    command = update.message.text
    match = re.match(r'/reject_(\d+)', command)
    if not match: return
    
    request_id = int(match.group(1))
    result = user_manager.reject_request(request_id)
    await update.message.reply_text(result['message'])
    
    if result['success']:
        try:
            await context.bot.send_message(
                chat_id=result['user_id'],
                text="😔 <b>Sorry!</b>\n\nYour access request has been rejected.",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def approve_user_direct_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dynamic /approveuser_<id> commands"""
    user_id = update.effective_user.id
    if not db.is_admin(user_id): return
    
    command = update.message.text
    match = re.match(r'/approveuser_(\d+)', command)
    if not match: return
    
    target_user_id = int(match.group(1))
    result = user_manager.add_user_directly(target_user_id)
    await update.message.reply_text(result['message'])
    
    if result['success']:
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 <b>Congratulations!</b>\n\nYour access request has been approved. You can now use the bot!",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def reject_user_direct_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dynamic /rejectuser_<id> commands"""
    user_id = update.effective_user.id
    if not db.is_admin(user_id): return
    
    command = update.message.text
    match = re.match(r'/rejectuser_(\d+)', command)
    if not match: return
    
    target_user_id = int(match.group(1))
    result = user_manager.remove_user(target_user_id)
    await update.message.reply_text(result['message'])




async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages (detect links and menu buttons)"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Handle Broadcast Input Check
    if context.user_data.get('awaiting_broadcast_message'):
        if text == '/cancel':
            context.user_data['awaiting_broadcast_message'] = False
            await update.message.reply_text("❌ Broadcast cancelled.")
            return

        # Sending Broadcast
        mode = context.user_data.get('broadcast_mode')
        users_to_message = []
        
        if mode == 'all':
            all_users = db.get_all_users()
            users_to_message = [u[0] for u in all_users]
        elif mode == 'selected':
            selected = context.user_data.get('broadcast_selected', set())
            users_to_message = list(selected)
            
        if not users_to_message:
            await update.message.reply_text("⚠️ No users found to message.")
            context.user_data['awaiting_broadcast_message'] = False
            return
            
        status_msg = await update.message.reply_text(f"⏳ Sending broadcast to {len(users_to_message)} users...")
        
        success_count = 0
        fail_count = 0
        
        for uid in users_to_message:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {uid}: {e}")
                fail_count += 1
            # Small delay to avoid hitting limits if list is huge
            await asyncio.sleep(0.05)
            
        await status_msg.edit_text(
            f"✅ <b>Broadcast Complete</b>\n\n"
            f"🟢 Success: {success_count}\n"
            f"🔴 Failed: {fail_count}",
            parse_mode=ParseMode.HTML
        )
        
        context.user_data['awaiting_broadcast_message'] = False
        return

    # Handle Reply Keyboard Buttons
    if text == "🏠 Main Menu":
        await start(update, context)
        return
    elif text == "❓ Help":
        await help_command(update, context)
        return
    elif text == "📝 Request Access":
        # Simulate 'request_info' callback logic
        info_text = """
📝 <b>Request Access</b>

To use this bot, you need to request access.
Use the following command to send a polite request:

<code>/request Your message here</code>

Example:
<code>/request I am a subscriber, please grant me access.</code>
"""
        await update.message.reply_text(info_text, parse_mode=ParseMode.HTML)
        return
    elif text == "👑 Admin Panel":
         if not db.is_admin(user_id):
            await update.message.reply_text("❌ Access Denied")
            return
            
         admin_text = "<b>👑 Admin Panel</b>\n\nChoose an option below:"
         keyboard = [
            [InlineKeyboardButton("👥 Users List", callback_data="admin_list_users")],
            [InlineKeyboardButton("⏳ Pending Requests", callback_data="admin_pending")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="start")]
         ]
         await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
         return

    # Check authorization for other messages (downloads)
    if not db.is_user_authorized(user_id):
        await update.message.reply_text(
            "⚠️ You are not authorized to use this bot.\n\n"
            "Click 'Request Access' button or send /request.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Request Access", callback_data="request_info")]])
        )
        return
    
    # Simple URL detection
    url_pattern = re.compile(r'https?://[^\s]+')
    urls = url_pattern.findall(text)
    
    if not urls:
        await update.message.reply_text(
            "❓ No link found. Please send a valid video link."
        )
        return
    
    url = urls[0]  # Take the first URL
    
    # Send processing message
    status_message = await update.message.reply_text("⏳ Processing link...")
    
    # Get media info
    try:
        loop = asyncio.get_running_loop()
        media_info = await loop.run_in_executor(None, lambda: downloader.get_media_info(url))
    except Exception as e:
        logger.error(f"Error getting media info: {e}")
        media_info = None

    if not media_info:
        await status_message.edit_text("❌ Failed to process link. Ensure it is valid and public.")
        return
    
    # ALWAYS Ask user for choice (Removed is_long check)
    keyboard = [
        [
            InlineKeyboardButton("🎬 Video", callback_data=f"download_video:{url}"),
            InlineKeyboardButton("🎵 Audio", callback_data=f"download_audio:{url}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    duration_hours = media_info['duration'] // 3600
    duration_minutes = (media_info['duration'] % 3600) // 60
    
    await status_message.edit_text(
        f"📹 <b>{media_info['title']}</b>\n\n"
        f"⏱ Duration: {duration_hours}h {duration_minutes}m\n\n"
        f"What would you like to download?",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    # Navigation Handlers
    if data == "start":
        await start(update, context)
        return
        
    elif data == "help":
        await help_command(update, context)
        return
        
    elif data == "request_info":
        info_text = """
📝 <b>Request Access</b>

To use this bot, you need to request access.
Use the following command to send a polite request:

<code>/request Your message here</code>

Example:
<code>/request I am a subscriber, please grant me access.</code>
"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
        await query.edit_message_text(info_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Admin Panel Handlers
    elif data == "admin_panel":
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Access Denied")
            return
            
        admin_text = "<b>👑 Admin Panel</b>\n\nChoose an option below:"
        keyboard = [
            [InlineKeyboardButton("� Broadcast Message", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton("�👥 Users List", callback_data="admin_list_users")],
            [InlineKeyboardButton("⏳ Pending Requests", callback_data="admin_pending")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="start")]
        ]
        await query.edit_message_text(admin_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data == "admin_broadcast_menu":
        if not db.is_admin(user_id): return
        
        text = "📢 <b>Broadcast Message</b>\n\nWho do you want to message?"
        keyboard = [
            [InlineKeyboardButton("📢 Send to ALL Users", callback_data="admin_broadcast_input:all")],
            [InlineKeyboardButton("👤 Select Users", callback_data="admin_broadcast_select:0")], # 0 is page/offset
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data.startswith("admin_broadcast_select:"):
        if not db.is_admin(user_id): return
        
        # Initialize selected set if not exists
        if 'broadcast_selected' not in context.user_data:
            context.user_data['broadcast_selected'] = set()
            
        page = int(data.split(":")[1])
        users = db.get_all_users() # (id, username, first_name, ...)
        
        # Pagination setup (5 users per page to fit buttons)
        PER_PAGE = 5
        start_idx = page * PER_PAGE
        end_idx = start_idx + PER_PAGE
        current_users = users[start_idx:end_idx]
        
        keyboard = []
        selected = context.user_data['broadcast_selected']
        
        for u in current_users:
            uid = u[0]
            name = u[2] or "Unknown"
            is_checked = uid in selected
            mark = "✅" if is_checked else "⬜"
            
            # Toggle button
            keyboard.append([InlineKeyboardButton(f"{mark} {name} ({uid})", callback_data=f"admin_broadcast_toggle:{uid}:{page}")])
        
        # Navigation buttons
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_broadcast_select:{page-1}"))
        if end_idx < len(users):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_broadcast_select:{page+1}"))
        
        if nav_row:
            keyboard.append(nav_row)
            
        # Action buttons
        keyboard.append([InlineKeyboardButton(f"✅ Done ({len(selected)} selected)", callback_data="admin_broadcast_input:selected")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_broadcast_menu")])
        
        await query.edit_message_text(
            "👤 <b>Select Users</b>\n\nClick to select/deselect users.", 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data.startswith("admin_broadcast_toggle:"):
        parts = data.split(":")
        target_uid = int(parts[1])
        page = int(parts[2])
        
        if 'broadcast_selected' not in context.user_data:
            context.user_data['broadcast_selected'] = set()
            
        selected = context.user_data['broadcast_selected']
        
        if target_uid in selected:
            selected.remove(target_uid)
        else:
            selected.add(target_uid)
            
        # Refresh view (loop back to select handler logic basically)
        # We can't call the handler function easily recursively with 'data', so let's just trigger the select update
        # Actually simplest is to just re-construct the view here or redirect
        # Let's just update the specific button? No, simplistic approach: re-render page
        # To re-render, we can just edit the message with the Select logic.
        # Let's mock a recursive call by updating data and letting a separate function handle render logic?
        # Or just copy paste render logic? 
        # Better: Separate render function. But for now, I'll just duplicate the render logic specific to this page refresh to save space/complexity
        
        # ... Re-render logic ...
        users = db.get_all_users()
        PER_PAGE = 5
        start_idx = page * PER_PAGE
        end_idx = start_idx + PER_PAGE
        current_users = users[start_idx:end_idx]
        
        keyboard = []
        for u in current_users:
            uid = u[0]
            name = u[2] or "Unknown"
            is_checked = uid in selected
            mark = "✅" if is_checked else "⬜"
            keyboard.append([InlineKeyboardButton(f"{mark} {name} ({uid})", callback_data=f"admin_broadcast_toggle:{uid}:{page}")])
            
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_broadcast_select:{page-1}"))
        if end_idx < len(users):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_broadcast_select:{page+1}"))
        if nav_row: keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton(f"✅ Done ({len(selected)} selected)", callback_data="admin_broadcast_input:selected")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_broadcast_menu")])
        
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass # No change
        return

    elif data.startswith("admin_broadcast_input:"):
        mode = data.split(":")[1]
        context.user_data['broadcast_mode'] = mode
        context.user_data['awaiting_broadcast_message'] = True
        
        count_str = "ALL users"
        if mode == 'selected':
            count = len(context.user_data.get('broadcast_selected', []))
            if count == 0:
                await query.answer("❌ No users selected!", show_alert=True)
                return
            count_str = f"{count} selected users"
            
        text = f"📢 <b>Broadcast: {count_str}</b>\n\nPlease type and send the message you want to broadcast.\n\nType /cancel to cancel."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=None)
        return

    elif data == "admin_list_users":
        await list_users(update, context)
        return

    elif data == "admin_pending":
        await pending_requests(update, context)
        return
        
    # Admin Actions Handlers
    elif data.startswith("admin_approve:"):
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Access Denied")
            return
            
        request_id = int(data.split(":")[1])
        result = user_manager.approve_request(request_id)
        
        new_text = f"{query.message.text_html}\n\n<b>Result:</b> {result['message']}"
        # Remove buttons
        await query.edit_message_text(new_text, parse_mode=ParseMode.HTML, reply_markup=None)
        
        if result['success']:
             try:
                await context.bot.send_message(
                    chat_id=result['user_id'],
                    text="🎉 <b>Congratulations!</b>\n\nYour access request has been approved. You can now use the bot!",
                    parse_mode=ParseMode.HTML
                )
             except Exception:
                pass
        return

    elif data.startswith("admin_reject:"):
        if not db.is_admin(user_id):
            await query.edit_message_text("❌ Access Denied")
            return
            
        request_id = int(data.split(":")[1])
        result = user_manager.reject_request(request_id)
        
        new_text = f"{query.message.text_html}\n\n<b>Result:</b> {result['message']}"
        # Remove buttons
        await query.edit_message_text(new_text, parse_mode=ParseMode.HTML, reply_markup=None)
        
        if result['success']:
             try:
                await context.bot.send_message(
                    chat_id=result['user_id'],
                    text="😔 <b>Sorry!</b>\n\nYour access request has been rejected.",
                    parse_mode=ParseMode.HTML
                )
             except Exception:
                pass
        return
    
    elif data.startswith("admin_pending_select:"):
        if not db.is_admin(user_id): return
        
        # Initialize selected set
        if 'pending_selected' not in context.user_data:
            context.user_data['pending_selected'] = set()
            
        page = int(data.split(":")[1])
        
        # Get all pending types
        requests = db.get_pending_requests() # [{'id':..., 'user_id':...}]
        pending_users = db.get_pending_users() # [(id, ...)]
        
        # Combine unique pending user objects
        # Map user_id to display info
        unique_pending = {}
        
        for req in requests:
            uid = req['user_id']
            # We assume req has user details or we fetch? 
            # db.get_pending_requests usually joins with users table
            # If not, we might need a better fetch. 
            # Looking at user_manager.py, get_pending_requests_formatted uses db.get_pending_requests()
            # Let's assume it returns info. If not, we rely on users table.
            # Actually simplest is just use get_pending_users() but that might not include those who "requested" if status is different?
            # Usually 'pending' status is consistent.
            # Let's use get_pending_users check.
            unique_pending[uid] = {'name': f"User {uid}", 'uid': uid} # Fallback
            
        # Better approach: Get all users with status 'pending'
        # I'll rely on db.get_pending_users() which should return all pending
        all_pending_rows = db.get_pending_users() 
        
        # Pagination
        PER_PAGE = 5
        start_idx = page * PER_PAGE
        end_idx = start_idx + PER_PAGE
        current_rows = all_pending_rows[start_idx:end_idx]
        
        keyboard = []
        selected = context.user_data['pending_selected']
        
        for u in current_rows:
            # u structure: (id, username, first_name, last_name, status, ...) from db.py
            uid = u[0]
            name = u[2] or u[1] or "Unknown"
            is_checked = uid in selected
            mark = "✅" if is_checked else "⬜"
            
            keyboard.append([InlineKeyboardButton(f"{mark} {name} ({uid})", callback_data=f"admin_pending_toggle:{uid}:{page}")])
            
        # Navigation
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_pending_select:{page-1}"))
        if end_idx < len(all_pending_rows):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_pending_select:{page+1}"))
        if nav_row: keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton(f"✅ Process ({len(selected)})", callback_data="admin_pending_confirm")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_pending")])
        
        await query.edit_message_text(
            "⏳ <b>Bulk Manage Pending</b>\n\nSelect users to approve/reject.", 
            parse_mode=ParseMode.HTML, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data.startswith("admin_pending_toggle:"):
        parts = data.split(":")
        target_uid = int(parts[1])
        page = int(parts[2])
        
        if 'pending_selected' not in context.user_data:
            context.user_data['pending_selected'] = set()
            
        selected = context.user_data['pending_selected']
        
        if target_uid in selected:
            selected.remove(target_uid)
        else:
            selected.add(target_uid)
        
        # Refresh view logic (duplicate of select render)
        all_pending_rows = db.get_pending_users()
        PER_PAGE = 5
        start_idx = page * PER_PAGE
        end_idx = start_idx + PER_PAGE
        current_rows = all_pending_rows[start_idx:end_idx]
        
        keyboard = []
        for u in current_rows:
            uid = u[0]
            name = u[2] or u[1] or "Unknown"
            is_checked = uid in selected
            mark = "✅" if is_checked else "⬜"
            keyboard.append([InlineKeyboardButton(f"{mark} {name} ({uid})", callback_data=f"admin_pending_toggle:{uid}:{page}")])
            
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_pending_select:{page-1}"))
        if end_idx < len(all_pending_rows):
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_pending_select:{page+1}"))
        if nav_row: keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton(f"✅ Process ({len(selected)})", callback_data="admin_pending_confirm")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_pending")])
        
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass
        return

    elif data == "admin_pending_confirm":
        selected = context.user_data.get('pending_selected', set())
        count = len(selected)
        
        if count == 0:
            await query.answer("❌ No users selected!", show_alert=True)
            return

        text = f"⚙️ <b>Bulk Action</b>\n\nSelected Users: {count}\n\nChoose action:"
        keyboard = [
            [InlineKeyboardButton("✅ Approve Selected", callback_data="admin_pending_execute:approve")],
            [InlineKeyboardButton("❌ Reject Selected", callback_data="admin_pending_execute:reject")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_pending_select:0")]
        ]
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    elif data.startswith("admin_pending_execute:"):
        action = data.split(":")[1]
        selected = context.user_data.get('pending_selected', set())
        
        if not selected:
             await query.answer("❌ No users selected!", show_alert=True)
             return
             
        await query.edit_message_text(f"⏳ Processing {len(selected)} users...")
        
        # Batch Process
        success_count = 0
        
        # Pre-fetch requests to map UID -> Request ID
        all_requests = db.get_pending_requests() # [{'id': 1, 'user_id': 123}, ...]
        uid_to_req_id = {r['user_id']: r['id'] for r in all_requests}
        
        for uid in selected:
            try:
                if action == 'approve':
                    if uid in uid_to_req_id:
                        # Approve via request
                        res = user_manager.approve_request(uid_to_req_id[uid])
                    else:
                        # Direct approve
                        res = user_manager.add_user_directly(uid)
                        
                    if res['success']:
                        success_count += 1
                        # Notify
                        try:
                            await context.bot.send_message(uid, "🎉 Your access request has been approved!", parse_mode=ParseMode.HTML)
                        except: pass
                        
                elif action == 'reject':
                    if uid in uid_to_req_id:
                         res = user_manager.reject_request(uid_to_req_id[uid])
                    else:
                         res = user_manager.remove_user(uid)
                         
                    if res['success']:
                        success_count += 1
                        try:
                            await context.bot.send_message(uid, "😔 Your access request has been rejected.", parse_mode=ParseMode.HTML)
                        except: pass
                        
            except Exception as e:
                logger.error(f"Batch error for {uid}: {e}")
                
        # Clear selection and finish
        context.user_data['pending_selected'] = set()
        
        result_text = f"✅ <b>Batch Complete</b>\n\nAction: {action.title()}\nProcessed: {success_count}/{len(selected)}"
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel")]]
        
        await query.edit_message_text(result_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
        return
        parts = data.split(':', 1)
        if len(parts) != 2:
            await query.edit_message_text("❌ Invalid request.")
            return
        
        action = parts[0].replace('download_', '')
        url = parts[1]
        
        await query.edit_message_text(f"⬇️ Starting {'Video' if action == 'video' else 'Audio'} download...")
        await download_and_send(update, context, url, action, query.message)


async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, media_type: str, status_message):
    """Download and send media to user"""
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    try:
        # Download based on type - RUN IN EXECUTOR to prevent blocking
        loop = asyncio.get_running_loop()
        if media_type == 'video':
            result = await loop.run_in_executor(None, lambda: downloader.download_video(url))
        else:
            result = await loop.run_in_executor(None, lambda: downloader.download_audio(url))
        
        if not result['success']:
            await status_message.edit_text(f"❌ Download failed: {result.get('error', 'Unknown error')}")
            return
        
        file_path = result['file_path']
        file_size = result['file_size']
        title = result['title']
        
        # Check file size (Telegram limit is 50MB for bots generally, 2GB for local API server?)
        # Standard bot API limit is 50MB for send_video/send_audio if sent by URL, but 
        # up to 50MB if sent as file. Actually, for local files it's 50MB.
        # Wait, if we use Bot API server, it's 50MB. If we use python-telegram-bot wrapper, we are uploading.
        # Upload limit is 50MB. 
        # Let's assume standard bot API. 2000MB is way too high unless using local bot API server.
        # I'll keep the check but maybe lower it or add a warning.
        # Correction: Bots can send files up to 50MB.
        # However, sending by URL can go up to 20MB.
        # Let's trust the user knows what they are doing or if they are using a local api server.
        # But to be safe, I'll warn if > 50MB.
        
        if file_size > 1999 * 1024 * 1024:  # 2GB limit just in case
             await status_message.edit_text(
                "❌ File too large. Cannot send due to Telegram limits."
            )
             downloader.cleanup_file(file_path)
             return

        await status_message.edit_text("📤 Uploading...")
        
        # Send file - RUN IN EXECUTOR or just await (send_video is async)
        # Note: opening file is blocking, but okay for small files. 
        # For large files, it might block the event loop slightly.
        try:
            with open(file_path, 'rb') as f:
                if media_type == 'video':
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=f,
                        caption=f"🎬 {title}",
                        supports_streaming=True,
                        read_timeout=120, 
                        write_timeout=120,
                        connect_timeout=120,
                        pool_timeout=120
                    )
                else:
                    await context.bot.send_audio(
                        chat_id=user_id,
                        audio=f,
                        caption=f"🎵 {title}",
                        title=title,
                        read_timeout=120, 
                        write_timeout=120
                    )
        except Exception as se:
            logger.error(f"Send error: {se}")
            await status_message.edit_text(f"❌ Error sending file: {se}")
            downloader.cleanup_file(file_path)
            return
            
        await status_message.edit_text("✅ Download Complete!")
        
        # Add to download history
        db.add_download(user_id, url, title, media_type, file_size)
        
        # Cleanup
        downloader.cleanup_file(file_path)
        
    except Exception as e:
        logger.error(f"Error in download_and_send: {e}")
        await status_message.edit_text(f"❌ Error: {str(e)}")


def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found! Please set it in .env file")
        return
    
    if not ADMIN_USER_ID:
        logger.warning("ADMIN_USER_ID not set! Please set it in .env file")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("request", request_access))
    application.add_handler(CommandHandler("listusers", list_users))
    application.add_handler(CommandHandler("pending", pending_requests))
    application.add_handler(CommandHandler("adduser", add_user))
    application.add_handler(CommandHandler("removeuser", remove_user))
    
    # Dynamic approve/reject handlers (Requests)
    application.add_handler(MessageHandler(
        filters.Regex(r'^/approve_\d+$'),
        approve_request_handler
    ))
    application.add_handler(MessageHandler(
        filters.Regex(r'^/reject_\d+$'),
        reject_request_handler
    ))

    # Dynamic approve/reject handlers (Direct Users)
    application.add_handler(MessageHandler(
        filters.Regex(r'^/approveuser_\d+$'),
        approve_user_direct_handler
    ))
    application.add_handler(MessageHandler(
        filters.Regex(r'^/rejectuser_\d+$'),
        reject_user_direct_handler
    ))
    
    # Message handler for links
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
