
from flask import Flask, render_template, request, redirect, session, url_for
import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from config import Config
from flask_session import Session

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "e3f1c2a5d5e1f2e4c9b6a4c8d3f0b7e6a8d5c3b9f4e2a1c7d6f0b8e5a4c2d3f1"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True

Session(app)  # Moved after app configuration

sp_oauth = SpotifyOAuth(
    client_id='7221b06d7bdf448cbe1cd4eaf3e4d779',
    client_secret='7ec66c2b674e4ba1a7dd79478f32f54c',
    redirect_uri="https://retro-production-7ee2.up.railway.app/callback",
    scope=os.getenv("SPOTIFY_SCOPE"),
)

import json  # Needed for string-to-dict conversion

def get_spotify_auth():
    token_info = session.get("token_info")

    print("Token Info:", token_info)  # Debugging

    if not token_info:
        return None  # No token available, user must log in

    if isinstance(token_info, str):  # Convert to dict if stored as a string
        token_info = json.loads(token_info)

    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info  # Save the refreshed token

    # ✅ Return an authenticated Spotipy client
    return spotipy.Spotify(auth=token_info["access_token"])


@app.route('/callback')
def callback():
    code = request.args.get("code")
    
    if not code:
        return "Authorization failed: No code received.", 400  # Handle missing code

    try:
        token_info = sp_oauth.get_access_token(code)  # Get access token (returns a dictionary)

        if not token_info or "access_token" not in token_info:
            return "Error retrieving access token.", 400

        session["token_info"] = token_info  # Store token info properly
        session.permanent = True  # Ensures session persists (optional)

        print("Stored Token Info:", session.get("token_info"))  # Debugging

        return redirect(url_for("dashboard"))

    except Exception as e:
        print(f"Error in callback: {e}")
        return "An error occurred during authentication.", 500


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)  # Redirect user to Spotify login


@app.route('/profile')
def profile():
    token_info = session.get('token_info', {})
    if not token_info:
        return redirect(url_for('login'))

    headers = {"Authorization": f"Bearer {token_info['access_token']}"}
    user_data = requests.get("https://api.spotify.com/v1/me", headers=headers).json()

    username = user_data.get('display_name', 'Unknown User')
    profile_image = user_data.get('images', [{}])[0].get('url', url_for('static', filename='profile.png'))

    return render_template('profile.html', username=username, profile_image=profile_image)


@app.route('/dashboard')
def dashboard():
    sp = get_spotify_auth()  # Get authenticated Spotipy client

    if not sp:
        return redirect(url_for("login"))  # Redirect if authentication fails

    try:
        user_data = sp.current_user()  # ✅ This will now work!
        
        # Handle missing 'images' field
        images = user_data.get('images', [])
        profile_image = images[0]['url'] if images else url_for('static', filename='profile.png')

        return render_template('dashboard.html', profile_image=profile_image)

    except Exception as e:
        print(f"Error fetching user data: {e}")
        return "An error occurred while fetching user data.", 500


@app.route('/playlist-to-personality')
def playlist_to_personality():
    return render_template('playlist_to_personality.html')



  # Show selection form on GET

@app.route('/select-playlist')
def select_playlist():
    """Fetches user's playlists and renders them in a dropdown list."""
    playlists = get_user_playlists()

    if not playlists:
        return render_template('select_playlist.html', error="No playlists found.")

    return render_template('select_playlist.html', playlists=playlists)


@app.route('/analyze-playlist', methods=['GET', 'POST'])
def analyze_playlist_personality():
    print("🚀 Function started!")

    # ✅ Retrieve token from session
    token_info = session.get('token_info')
    if not token_info:
        print("❌ No token found. Redirecting to login.")
        return redirect(url_for("login"))

    sp = spotipy.Spotify(auth=token_info['access_token'])

    if request.method == 'POST':
        playlist_id = request.form.get('playlist_id')
        if not playlist_id:
            print("⚠️ No playlist selected.")
            return render_template('select_playlist.html', error="Please select a playlist.")

        print(f"🔍 Selected Playlist ID: {playlist_id}")
        df_tracks = get_playlist_tracks_with_genres(playlist_id)

        # ✅ Ensure df_tracks is a DataFrame
        if not isinstance(df_tracks, pd.DataFrame) or df_tracks.empty:
            print("⚠️ No tracks found in the playlist.")
            return render_template('analyze_playlist.html', error="No tracks found in the selected playlist.")

        # ✅ Use absolute paths for dataset files
        base_dir = os.path.abspath(os.path.dirname(__file__))  
        dataset_path = os.path.join(base_dir, "data", "dataset.csv")
        mapping_path = os.path.join(base_dir, "data", "mapping.csv")

        print(f"📂 Checking dataset files at:\n- {dataset_path}\n- {mapping_path}")

        # ✅ Check if dataset files exist
        if not os.path.exists(dataset_path) or not os.path.exists(mapping_path):
            print("❌ Dataset files not found.")
            return render_template('analyze_playlist.html', error="Dataset files not found.")

        print("📂 Loading dataset files...")
        features_df = pd.read_csv(dataset_path)
        p_df = pd.read_csv(mapping_path)

        # ✅ Ensure datasets are not empty
        if features_df.empty or p_df.empty:
            print("❌ Dataset files are empty or incorrectly formatted.")
            return render_template('analyze_playlist.html', error="Dataset files are empty or incorrectly formatted.")

        # ✅ Convert track IDs to string before mapping
        df_tracks['track_id'] = df_tracks['track_id'].astype(str)
        features_df['track_id'] = features_df['track_id'].astype(str)

        # ✅ Match track genres
        genre_dict = dict(zip(features_df['track_id'], features_df['track_genre']))
        df_tracks['track_genre'] = df_tracks['track_id'].map(genre_dict).fillna("Unknown")

        print("🎶 Calculating genre distribution...")
        genre_counts = df_tracks['track_genre'].value_counts(normalize=True) * 100
        genre_percentage_df = pd.DataFrame({'genre': genre_counts.index, 'percentage': genre_counts.values})

        # ✅ Define personality trait mapping
        trait_mapping = {
            'Extraversion': 'Extroverted',
            'Openness to Experience': 'Creative',
            'Conscientiousness': 'Hardworking',
            'Self-Esteem': 'Confident',
            'Neuroticism': 'Anxious',
            'Introversion': 'Introverted',
            'Agreeableness': 'Agreeable',
            'Low Self-Esteem': 'Low Self-Esteem',
            'Gentle': 'Gentle',
            'Assertive': 'Bold',
            'Emotionally Stable': 'Emotionally Stable',
            'Intellectual': 'Intellectual',
            'At Ease': 'Calm'
        }

        # ✅ Calculate personality traits
        print("🧠 Mapping genres to personality traits...")
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

        print("📊 Generating personality dataframe...")
        personality_df = pd.DataFrame(list(user_personality.items()), columns=['Trait', 'Score'])
        personality_df = personality_df.sort_values(by='Score', ascending=False)

        # ✅ Generate personality pie chart
        print("📈 Creating personality chart...")
        filtered_personality = {k: v for k, v in user_personality.items() if v > 0}
        chart_path = None

        if filtered_personality:
            plt.figure(figsize=(8, 8))
            plt.pie(filtered_personality.values(), labels=filtered_personality.keys(), autopct='%1.1f%%', colors=plt.cm.Paired.colors)
            plt.title("User's Personality Traits Based on Playlist")
            plt.axis('equal')

            # ✅ Ensure `static/` folder exists
            static_dir = os.path.join(base_dir, 'static')
            if not os.path.exists(static_dir):
                os.makedirs(static_dir)

            chart_path = os.path.join(static_dir, 'personality_chart.png')
            plt.savefig(chart_path)
            plt.close()

            # ✅ Update the chart URL for HTML rendering
            chart_url = "/static/personality_chart.png"
            print(f"📸 Chart saved at: {chart_url}")

        print("✅ Rendering results.")
        return render_template('analyze_playlist.html', personality_df=personality_df.to_html(), chart_url=chart_url)

    # If GET request, just show the form
    playlists = get_user_playlists()
    return render_template('analyze_playlist.html', playlists=playlists)


def get_user_playlists():
    """Fetch the current user's playlists."""
    token_info = session.get("token_info")
    if not token_info:
        print("❌ No token found. Redirecting to login.")
        return []

    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        playlists = sp.current_user_playlists().get('items', [])

        if not playlists:
            print("⚠️ No playlists found.")
            return []

        return [{'name': p['name'], 'id': p['id']} for p in playlists]

    except Exception as e:
        print(f"❌ Error fetching playlists: {e}")
        return []
def get_playlist_id_by_name(playlist_name):
    """Find a playlist ID by name."""
    token_info = session.get("token_info")
    if not token_info:
        print("❌ No token found. Redirecting to login.")
        return None

    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        playlists = sp.current_user_playlists().get('items', [])

        for playlist in playlists:
            if playlist['name'].lower() == playlist_name.lower():
                return playlist['id']

        print(f"⚠️ Playlist '{playlist_name}' not found.")
        return None

    except Exception as e:
        print(f"❌ Error finding playlist: {e}")
        return None
def get_playlist_tracks_with_genres(playlist_id):
    """Retrieve tracks from a playlist and return as a DataFrame."""
    token_info = session.get("token_info")
    if not token_info:
        print("❌ No token found. Redirecting to login.")
        return pd.DataFrame()  # ✅ Return an empty DataFrame instead of a list

    try:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        tracks_data = sp.playlist_tracks(playlist_id).get('items', [])

        if not tracks_data:
            print("⚠️ No tracks found in the playlist.")
            return pd.DataFrame()  # ✅ Return an empty DataFrame instead of a list

        track_details = []
        for track in tracks_data:
            if 'track' in track and track['track']:  # ✅ Ensure 'track' exists
                track_info = track['track']
                track_details.append({
                    'track_id': track_info['id'],
                    'track_name': track_info['name'],
                    'artist': track_info['artists'][0]['name'],
                    'album_name': track_info['album']['name'],
                    'popularity': track_info['popularity'],
                    'duration_ms': track_info['duration_ms'],
                    'explicit': track_info['explicit'],
                })

        return pd.DataFrame(track_details)  # ✅ Convert list to Pandas DataFrame

    except Exception as e:
        print(f"❌ Error fetching tracks: {e}")
        return pd.DataFrame()  # ✅ Ensure it returns a DataFrame, not a list





if __name__ == "__main__":
    from os import getenv
    app.run(host="0.0.0.0", port=int(getenv("PORT", 5000)))

