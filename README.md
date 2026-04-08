# SpotifyToLFM.py

Modified from reddit snippet - incomplete but now uses environment variables from a `.env` file for API credentials.

## Setup

1. Copy `.env.example` to `.env`.
2. Fill in your Last.fm and Spotify credentials.
3. Install dependencies and run:

```bash
uv sync
uv run python main.py
```

Required variables:

- `LASTFM_API_KEY`
- `LASTFM_API_SECRET`
- `SPOTIPY_CLIENT_ID`
- `SPOTIPY_CLIENT_SECRET`

