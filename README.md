# SpotifyToLFM.py

A Python script to scrobble Spotify tracks, albums, and playlists to Last.fm.

## Setup

### 1. Install Dependencies

This project uses `uv` for dependency management. Install dependencies with:

```bash
uv sync
```

Or with pip:

```bash
pip install pylast spotipy python-dotenv
```

### 2. Configure API Credentials

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your API credentials in the `.env` file:
   - **Last.fm API**: Get your API key and secret from https://www.last.fm/api/account/create
   - **Spotify API**: Get your client ID and secret from https://developer.spotify.com/dashboard
   - **Scrobble Offset**: Set the number of seconds ago to start scrobbling (default: 0)

### 3. Run the Script

```bash
python main.py
```

On first run, you'll be prompted to authorize the script to access your Last.fm account.

## Usage

After running the script, you can paste Spotify links for:
- Individual tracks
- Albums
- Playlists

The script will scrobble the tracks to your Last.fm account with the appropriate timestamps.
 
