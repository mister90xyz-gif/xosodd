#!/bin/bash
# Startup script for the Telegram bot

# Navigate to bot directory
cd "$(dirname "$0")"

# Check if .env file exists and has credentials
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with your BOT_TOKEN and ADMIN_USER_ID"
    exit 1
fi

# Check if BOT_TOKEN is set
if grep -q "paste_your_bot_token_here" .env; then
    echo "❌ Error: BOT_TOKEN not configured!"
    echo "Please edit .env file and add your actual bot token from @BotFather"
    exit 1
fi

# Check if ADMIN_USER_ID is set
if grep -q "paste_your_user_id_here" .env; then
    echo "❌ Error: ADMIN_USER_ID not configured!"
    echo "Please edit .env file and add your actual user ID from @userinfobot"
    exit 1
fi

echo "🔧 Checking database..."
if [ ! -f bot_database.db ]; then
    echo "📊 Initializing database..."
    ./venv/bin/python init_db.py
fi

echo "🚀 Starting Telegram bot..."
echo "Press Ctrl+C to stop the bot"
echo ""

./venv/bin/python bot.py
