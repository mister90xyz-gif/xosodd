import yt_dlp
import os
from config import DOWNLOAD_FOLDER, MAX_FILE_SIZE_MB, LONG_VIDEO_THRESHOLD

class MediaDownloader:
    def __init__(self):
        self.download_folder = DOWNLOAD_FOLDER
    
    def get_media_info(self, url):
        """Get information about the media without downloading"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                duration = info.get('duration', 0)
                title = info.get('title', 'Unknown')
                
                return {
                    'title': title,
                    'duration': duration,
                    'is_long': duration > LONG_VIDEO_THRESHOLD,
                    'url': url
                }
        except Exception as e:
            print(f"Error getting media info: {e}")
            return None
    
    def download_video(self, url, progress_callback=None):
        """Download video from URL"""
        output_template = os.path.join(self.download_folder, '%(title)s.%(ext)s')
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_callback] if progress_callback else [],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                return {
                    'success': True,
                    'file_path': filename,
                    'title': info.get('title', 'Unknown'),
                    'file_size': os.path.getsize(filename) if os.path.exists(filename) else 0
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_audio(self, url, progress_callback=None):
        """Download audio only from URL"""
        output_template = os.path.join(self.download_folder, '%(title)s.%(ext)s')
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'progress_hooks': [progress_callback] if progress_callback else [],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Get the filename after audio extraction
                filename = ydl.prepare_filename(info)
                # Replace extension with mp3
                filename = os.path.splitext(filename)[0] + '.mp3'
                
                return {
                    'success': True,
                    'file_path': filename,
                    'title': info.get('title', 'Unknown'),
                    'file_size': os.path.getsize(filename) if os.path.exists(filename) else 0
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_file(self, file_path):
        """Remove downloaded file after sending"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            print(f"Error cleaning up file: {e}")
        return False
