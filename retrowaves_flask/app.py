from flask import Flask, render_template, request, redirect, session, url_for
import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from flask_caching import Cache  # Added caching
from config import Config

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)  # Load configuration from config.py

# Configure caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Spotify Authentication Setup
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    redirect_uri=os.getenv("REDIRECT_URI"),
    scope=os.getenv("SPOTIFY_SCOPE"),
)

def get_spotify_auth():
    """Retrieve and refresh Spotify access token."""
    token_info = session.get("token_info")
    if not token_info:
        return None

    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session["token_info"] = token_info  # Update session with new token

    return spotipy.Spotify(auth=token_info['access_token'])

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """Handle Spotify OAuth callback and store token info."""
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('dashboard'))

@app.route('/profile')
def profile():
    sp = get_spotify_auth()
    if not sp:
        return redirect(url_for('login'))

    user_data = sp.me()
    username = user_data.get('display_name', 'Unknown User')
    profile_image = user_data.get('images', [{}])[0].get('url', url_for('static', filename='profile.png'))

    return render_template('profile.html', username=username, profile_image=profile_image)

@app.route('/dashboard')
def dashboard():
    sp = get_spotify_auth()
    if not sp:
        return redirect(url_for('login'))

    user_data = sp.me()
    username = user_data.get('display_name', 'Spotify User')
    profile_image = user_data.get('images', [{}])[0].get('url', url_for('static', filename='profile.png'))

    return render_template('dashboard.html', username=username, profile_image=profile_image)

@app.route('/playlist-to-personality')
def playlist_to_personality():
    return render_template('playlist_to_personality.html')

@app.route('/select-playlist')
def select_playlist():
    playlists = get_user_playlists()
    if not playlists:
        return render_template('select_playlist.html', error="No playlists found.")
    return render_template('select_playlist.html', playlists=playlists)

@app.route('/analyze-playlist', methods=['GET', 'POST'])
def analyze_playlist_personality():
    sp = get_spotify_auth()
    if not sp:
        return redirect(url_for("login"))

    if request.method == 'POST':
        playlist_id = request.form.get('playlist_id')
        if not playlist_id:
            return render_template('select_playlist.html', error="Please select a playlist.")

        df_tracks = get_playlist_tracks_with_genres(playlist_id)
        if df_tracks.empty:
            return render_template('analyze_playlist.html', error="No tracks found in the selected playlist.")

        base_dir = os.path.abspath(os.path.dirname(__file__))
        dataset_path = os.path.join(base_dir, "data", "dataset.csv")
        mapping_path = os.path.join(base_dir, "data", "mapping.csv")

        # Check dataset files
        if not os.path.exists(dataset_path) or not os.path.exists(mapping_path):
            return render_template('analyze_playlist.html', error="Dataset files not found.")

        features_df = pd.read_csv(dataset_path)
        p_df = pd.read_csv(mapping_path)

        if features_df.empty or p_df.empty:
            return render_template('analyze_playlist.html', error="Dataset files are empty or incorrectly formatted.")

        # Map track IDs to genres
        df_tracks['track_id'] = df_tracks['track_id'].astype(str)
        features_df['track_id'] = features_df['track_id'].astype(str)
        genre_dict = dict(zip(features_df['track_id'], features_df['track_genre']))
        df_tracks['track_genre'] = df_tracks['track_id'].map(genre_dict).fillna("Unknown")

        # Genre distribution
        genre_counts = df_tracks['track_genre'].value_counts(normalize=True) * 100
        genre_percentage_df = pd.DataFrame({'genre': genre_counts.index, 'percentage': genre_counts.values})

        # Personality trait mapping
        trait_mapping = {
            'Extraversion': 'Extroverted', 'Openness to Experience': 'Creative', 'Conscientiousness': 'Hardworking',
            'Self-Esteem': 'Confident', 'Neuroticism': 'Anxious', 'Introversion': 'Introverted',
            'Agreeableness': 'Agreeable', 'Low Self-Esteem': 'Low Self-Esteem', 'Gentle': 'Gentle',
            'Assertive': 'Bold', 'Emotionally Stable': 'Emotionally Stable', 'Intellectual': 'Intellectual',
            'At Ease': 'Calm'
        }

        user_personality = {trait: 0 for trait in trait_mapping.values()}
        p_df['Genre'] = p_df['Genre'].str.title()
        genre_percentage_df['genre'] = genre_percentage_df['genre'].str.title()

        for _, row in genre_percentage_df.iterrows():
            genre = row['genre']
            percentage = row['percentage']
            if genre in p_df['Genre'].values:
                genre_traits = p_df[p_df['Genre'] == genre].iloc[0, 1:]
                for trait, value in genre_traits.items():
                    if pd.notna(value) and trait in trait_mapping:
                        user_personality[trait_mapping[trait]] += value * (percentage / 100)

        personality_df = pd.DataFrame(list(user_personality.items()), columns=['Trait', 'Score']).sort_values(by='Score', ascending=False)

        # Generate pie chart
        filtered_personality = {k: v for k, v in user_personality.items() if v > 0}
        chart_path = None
        if filtered_personality:
            plt.figure(figsize=(8, 8))
            plt.pie(filtered_personality.values(), labels=filtered_personality.keys(), autopct='%1.1f%%', colors=plt.cm.Paired.colors)
            plt.title("User's Personality Traits Based on Playlist")
            plt.axis('equal')

            static_dir = os.path.join(base_dir, 'static')
            os.makedirs(static_dir, exist_ok=True)

            chart_path = os.path.join(static_dir, 'personality_chart.png')
            plt.savefig(chart_path)
            plt.close()

        return render_template('analyze_playlist.html', personality_df=personality_df.to_html(), chart_url="/static/personality_chart.png")

    playlists = get_user_playlists()
    return render_template('analyze_playlist.html', playlists=playlists)

@cache.memoize(timeout=600)
def get_user_playlists():
    """Fetch user's playlists with caching."""
    sp = get_spotify_auth()
    if not sp:
        return []

    playlists = sp.current_user_playlists().get('items', [])
    return [{'name': p['name'], 'id': p['id']} for p in playlists]

@cache.memoize(timeout=600)
def get_playlist_tracks_with_genres(playlist_id):
    """Fetch all tracks from a playlist with pagination."""
    sp = get_spotify_auth()
    if not sp:
        return pd.DataFrame()

    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        tracks.extend(results['items'])
        results = sp.next(results) if results['next'] else None

    return pd.DataFrame([{
        'track_id': t['track']['id'], 'track_name': t['track']['name'],
        'artist': t['track']['artists'][0]['name'], 'album_name': t['track']['album']['name']
    } for t in tracks if 'track' in t])




if __name__ == "__main__":
    from os import getenv
    app.run(host="0.0.0.0", port=int(getenv("PORT", 5000)))

