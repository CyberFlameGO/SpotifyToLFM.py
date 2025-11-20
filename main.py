import os
import re
import sys
import time
import webbrowser
from pathlib import Path

import pylast
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

# Load environment variables from .env file
load_dotenv()

################################################################################################
# Load configuration from environment variables
API_KEY = os.getenv("LASTFM_API_KEY")
API_SECRET = os.getenv("LASTFM_API_SECRET")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
offset = int(os.getenv("SCROBBLE_OFFSET", "0"))

# Validate that all required environment variables are set
required_vars = {
    "LASTFM_API_KEY": API_KEY,
    "LASTFM_API_SECRET": API_SECRET,
    "SPOTIFY_CLIENT_ID": SPOTIPY_CLIENT_ID,
    "SPOTIFY_CLIENT_SECRET": SPOTIPY_CLIENT_SECRET,
}

missing_vars = [var_name for var_name, var_value in required_vars.items() if not var_value]
if missing_vars:
    print("Error: Missing required environment variables:")
    for var in missing_vars:
        print(f"  - {var}")
    print("\nPlease create a .env file based on .env.example and fill in your credentials.")
    sys.exit(1)
################################################################################################

# This snippet is from pylast as an alternative to writing credentials to variables

SESSION_KEY_FILE = Path.home() / ".session_key"
network = pylast.LastFMNetwork(API_KEY, API_SECRET)
if not SESSION_KEY_FILE.exists():
    skg = pylast.SessionKeyGenerator(network)
    url = skg.get_web_auth_url()

    print(f"Please authorize this script to access your account: {url}\n")

    webbrowser.open(url)

    while True:
        try:
            session_key = skg.get_web_auth_session_key(url)
            SESSION_KEY_FILE.write_text(session_key)
            break
        except pylast.WSError:
            time.sleep(1)
else:
    session_key = SESSION_KEY_FILE.read_text()

network.session_key = session_key

auth_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=auth_manager)


# takes in a spotify link and returns the link type and ID
def parse(spotify_link):
    link = re.search(r"https:\/\/open\.spotify\.com\/([a-zA-Z]+)\/([a-zA-Z0-9]+)", spotify_link)
    if link:
        link_type = link.group(1)
        link_id = link.group(2)
        return link_type, link_id


def scrobble(artist, album, track, timestamp=None, albumartist=""):
    if timestamp is None:
        timestamp = time.time()
    if albumartist == "":
        albumartist = artist
    network.scrobble(artist=artist, album=album, title=track, timestamp=int(timestamp), album_artist=albumartist)
    timestamp_str = time.strftime('%m/%d/%y %H:%M:%S', time.localtime(timestamp))
    print(f"Scrobbled {track} by {artist} at {timestamp_str}")


def get_track_and_scrobble(link_id, timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    trackinfo = sp.track(link_id)
    track = trackinfo["name"]
    album = trackinfo["album"]["name"]
    artist = trackinfo["artists"][0]["name"]
    albumartist = trackinfo["album"]["artists"][0]["name"]
    scrobble(artist=artist, album=album, track=track, albumartist=albumartist, timestamp=timestamp)
    return trackinfo["duration_ms"]


def scrobble_list(listinfo, listtype, timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    # handles album or playlist
    totaltime = 0
    for item in listinfo["items"]:
        if listtype == "playlist":
            totaltime += item["track"]["duration_ms"]
        elif listtype == "album":
            totaltime += item["duration_ms"]
    timestamp = timestamp - round(totaltime / 1000)
    for item in listinfo["items"]:
        if listtype == "playlist":
            itemlink = item["track"]["external_urls"]["spotify"]
        elif listtype == "album":
            itemlink = item["external_urls"]["spotify"]
        else:
            print("How did you get here?")
            return 0
        link_type, link_id = parse(itemlink)
        length = get_track_and_scrobble(link_id, timestamp)
        timestamp = timestamp + round(length / 1000)


def main(link, timestamp=None):
    if timestamp is None:
        timestamp = time.time()
    link_type, link_id = parse(link)
    if link_type == "playlist":
        playlistinfo = sp.playlist_items(link_id)
        scrobble_list(playlistinfo, "playlist", timestamp)
    elif link_type == "album":
        albuminfo = sp.album_tracks(link_id)
        scrobble_list(albuminfo, "album", timestamp)
    elif link_type == "track":
        get_track_and_scrobble(link_id, timestamp)
    else:
        print("Link must be either playlist, album, or track")


# TODO - ADD PROPER CHECKS FOR INPUT
if __name__ == "__main__":
    while True:
        spotifylink = input("link: ")  # paste spotify link here; can be playlist, album, or single track
        main(spotifylink, time.time() - offset)
