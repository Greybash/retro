import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    DEBUG = True

    # Static files
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    STATIC_FOLDER = os.path.join(BASE_DIR, "static")

    # Session settings
    SESSION_COOKIE_AGE = 86400  # 1 day
    SESSION_PERMANENT = True

    # Spotify API Credentials
    CLIENT_ID = '7221b06d7bdf448cbe1cd4eaf3e4d779'
    CLIENT_SECRET = '7ec66c2b674e4ba1a7dd79478f32f54c'
    REDIRECT_URI = 'https://your-app-name.up.railway.app/callback'
    SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
    SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
    SPOTIFY_SCOPE = "user-read-private user-read-email user-library-modify user-library-read streaming app-remote-control playlist-read-collaborative playlist-modify-private playlist-modify-public user-top-read"
    SPOTIFY_CACHE_PATH = os.path.join(BASE_DIR, ".spotify_cache")

    # Database (SQLite example)
    DATABASE_URI = os.path.join(BASE_DIR, "db.sqlite3")
