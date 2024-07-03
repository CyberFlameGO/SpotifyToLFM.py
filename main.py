import os
import re
import pylast
import time
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

################################################################################################
# Fill out everything between the hashtags
API_KEY = ""  # your last.fm API key
API_SECRET = ""  # your last.fm API secret
SPOTIPY_CLIENT_ID = ""  # your spotify API key
SPOTIPY_CLIENT_SECRET = ""  # your spotify API secret

offset = 22813  # number of seconds ago to start scrobbling
################################################################################################

# This snippet is from pylast as an alternative to writing credentials to variables

SESSION_KEY_FILE = os.path.join(os.path.expanduser("~"), ".session_key")
network = pylast.LastFMNetwork(API_KEY, API_SECRET)
if not os.path.exists(SESSION_KEY_FILE):
    skg = pylast.SessionKeyGenerator(network)
    url = skg.get_web_auth_url()

    print(f"Please authorize this script to access your account: {url}\n")
    import time
    import webbrowser

    webbrowser.open(url)

    while True:
        try:
            session_key = skg.get_web_auth_session_key(url)
            with open(SESSION_KEY_FILE, "w") as f:
                f.write(session_key)
            break
        except pylast.WSError:
            time.sleep(1)
else:
    session_key = open(SESSION_KEY_FILE).read()

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


def scrobble(artist, album, track, timestamp=time.time(), albumartist=""):
    if albumartist == "":
        albumartist = artist
    network.scrobble(artist=artist, album=album, title=track, timestamp=timestamp, album_artist=albumartist)
    print(f"Scrobbled {track} by {artist} at {time.strftime('%m/%d/%y %H:%M:%S', time.localtime(timestamp))}")


def get_track_and_scrobble(link_id, timestamp=time.time()):
    trackinfo = sp.track(link_id)
    track = trackinfo["name"]
    album = trackinfo["album"]["name"]
    artist = trackinfo["artists"][0]["name"]
    albumartist = trackinfo["album"]["artists"][0]["name"]
    scrobble(artist=artist, album=album, track=track, albumartist=albumartist, timestamp=timestamp)
    return trackinfo["duration_ms"]


def scrobble_list(listinfo, listtype, timestamp=time.time()):
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


def main(link, timestamp=time.time()):
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
while True:
    spotifylink = input("link: ")  # paste spotify link here; can be playlist, album, or single track
    main(spotifylink, time.time() - offset)
