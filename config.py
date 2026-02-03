import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot_database.db')

# Download Configuration
MAX_FILE_SIZE_MB = 2000  # Maximum file size in MB (PythonAnywhere has limits)
DOWNLOAD_FOLDER = 'downloads'
LONG_VIDEO_THRESHOLD = 60  # 1 hour in seconds

# Create downloads folder if it doesn't exist
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
