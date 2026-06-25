import os
import re
import queue
import threading
import pylast
import time
import spotipy
import webbrowser
from contextlib import suppress
from pathlib import Path
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

if not load_dotenv():
    print("No .env variables set. This app will not work as expected")


def get_required_env(name: str) -> str:
    if not (value := os.getenv(name)):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


LASTFM_API_KEY = get_required_env("LASTFM_API_KEY")
LASTFM_API_SECRET = get_required_env("LASTFM_API_SECRET")
SPOTIPY_CLIENT_ID = get_required_env("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = get_required_env("SPOTIPY_CLIENT_SECRET")
offset = 982516

# This snippet is from pylast as an alternative to writing credentials to variables

SESSION_KEY_FILE = Path(".session_key")
network = pylast.LastFMNetwork(LASTFM_API_KEY, LASTFM_API_SECRET)

if not SESSION_KEY_FILE.exists():
    skg = pylast.SessionKeyGenerator(network)
    url = skg.get_web_auth_url()

    print(f"Please authorize this script to access your account: {url}\n")

    if not webbrowser.open(url):
        print("Please open the following URL in your browser to authorize this script:")
        print(url)

    while True:
        try:
            session_key: str = skg.get_web_auth_session_key(url)
            SESSION_KEY_FILE.write_text(session_key)
            break
        except pylast.WSError:
            time.sleep(1)
else:
    session_key = SESSION_KEY_FILE.read_text()

network.session_key = session_key

auth_manager = SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET
)
sp = spotipy.Spotify(auth_manager=auth_manager)


def parse(spotify_link: str) -> tuple[str, str]:
    """
    Parses a Spotify link to extract the link type and ID.
    Raises ValueError if the link is not a valid Spotify URL.
    """
    if link := re.search(
        r"https://open\.spotify\.com/([a-zA-Z]+)/([a-zA-Z0-9]+)", spotify_link
    ):
        return link.group(1), link.group(2)
    raise ValueError("Invalid Spotify link")


def scrobble(
    artist: str,
    album: str,
    track: str,
    timestamp: int | float | None = None,
    album_artist: str = "",
) -> None:
    """Scrobbles a track to Last.fm."""
    album_artist = album_artist or artist
    timestamp = time.time() if timestamp is None else timestamp
    if isinstance(timestamp, float):
        timestamp = int(timestamp)

    network.scrobble(
        artist=artist,
        album=album,
        title=track,
        timestamp=timestamp,
        album_artist=album_artist,
    )
    time_str = time.strftime('%m/%d/%y %H:%M:%S', time.localtime(timestamp))
    print(f"Scrobbled {track} by {artist} at {time_str}")


def get_track_and_scrobble(
    link_id: str, timestamp: float | None = None
) -> int:
    """Gets track information from Spotify and scrobbles it."""
    timestamp = time.time() if timestamp is None else timestamp
    if not (track_info := sp.track(link_id)):
        print(f"Could not find track with ID: {link_id}")
        return 0

    track_name = track_info.get("name")
    album_info = track_info.get("album")
    artists_info = track_info.get("artists")
    duration = track_info.get("duration_ms")

    if not (
        isinstance(track_name, str)
        and isinstance(album_info, dict)
        and isinstance(artists_info, list)
        and artists_info
        and isinstance(duration, int)
    ):
        print(f"Track info for {link_id} is missing required fields. Skipping.")
        return 0

    album_name = album_info.get("name")
    album_artists_info = album_info.get("artists")
    artist_name = artists_info[0].get("name")

    if not (isinstance(album_artists_info, list) and album_artists_info):
        print(f"Track info for {link_id} is missing album artist fields. Skipping.")
        return 0
    album_artist_name = album_artists_info[0].get("name")

    if not (
        isinstance(album_name, str)
        and isinstance(artist_name, str)
        and isinstance(album_artist_name, str)
    ):
        print(f"Track info for {link_id} is missing nested name fields. Skipping.")
        return 0

    scrobble(
        artist=artist_name,
        album=album_name,
        track=track_name,
        album_artist=album_artist_name,
        timestamp=timestamp,
    )
    return duration


def scrobble_list(
    list_info: dict[str, list[dict[str, object]]] | None,
    list_type: str,
    timestamp: float | None = None,
) -> None:
    """Scrobbles a playlist or album."""
    timestamp = time.time() if timestamp is None else timestamp
    if not list_info or "items" not in list_info:
        print(f"Could not retrieve items for the {list_type}.")
        return

    items = list_info["items"]
    if not isinstance(items, list):
        print(f"Expected a list of items for {list_type}, but got something else.")
        return

    total_time = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        with suppress(TypeError, KeyError):
            match list_type:
                case "playlist":
                    track_item = item.get("track")
                    if isinstance(track_item, dict):
                        if isinstance(duration := track_item.get("duration_ms"), int):
                            total_time += duration
                case "album":
                    if isinstance(duration := item.get("duration_ms"), int):
                        total_time += duration

    timestamp -= round(total_time / 1000)

    for item in items:
        if not isinstance(item, dict):
            continue

        item_link = None
        with suppress(TypeError, KeyError):
            match list_type:
                case "playlist":
                    track_item = item.get("track")
                    if isinstance(track_item, dict):
                        external_urls = track_item.get("external_urls")
                        if isinstance(external_urls, dict):
                            item_link = external_urls.get("spotify")
                case "album":
                    external_urls = item.get("external_urls")
                    if isinstance(external_urls, dict):
                        item_link = external_urls.get("spotify")

        if not isinstance(item_link, str):
            print("Skipping an item with no Spotify link.")
            continue

        try:
            _, link_id = parse(item_link)
            if (length := get_track_and_scrobble(link_id, timestamp)) > 0:
                timestamp += round(length / 1000)
        except ValueError:
            print(f"Skipping invalid link: {item_link}")


def process_link(link: str, timestamp: float | None = None) -> None:
    """Processes a single Spotify link."""
    timestamp = time.time() if timestamp is None else timestamp
    try:
        link_type, link_id = parse(link)
        match link_type:
            case "playlist":
                playlist_info = sp.playlist_items(link_id)
                scrobble_list(playlist_info, "playlist", timestamp)
            case "album":
                album_info = sp.album_tracks(link_id)
                scrobble_list(album_info, "album", timestamp)
            case "track":
                get_track_and_scrobble(link_id, timestamp)
            case _:
                print("Link must be either playlist, album, or track")
    except (ValueError, spotipy.exceptions.SpotifyException) as e:
        print(f"Error processing link: {link} - {e}")


def scrobble_worker(q: queue.Queue[tuple[str, float] | None]) -> None:
    """Worker thread to process scrobbles from a queue."""
    while True:
        if (item := q.get()) is None:
            break
        link, timestamp = item
        process_link(link, timestamp)
        q.task_done()


if __name__ == "__main__":
    scrobble_queue: queue.Queue[tuple[str, float] | None] = queue.Queue()
    worker_thread = threading.Thread(target=scrobble_worker, args=(scrobble_queue,))
    worker_thread.start()

    print("Paste Spotify links (separated by newlines or spaces). Press Enter twice to finish.")
    while True:
        try:
            if not (line := input()).strip():
                break
            for spotify_link in line.split():
                if spotify_link.strip():
                    scrobble_queue.put((spotify_link.strip(), time.time() - offset))
        except (EOFError, KeyboardInterrupt):
            break

    scrobble_queue.put(None)
    worker_thread.join()
    print("All scrobbles have been processed.")
