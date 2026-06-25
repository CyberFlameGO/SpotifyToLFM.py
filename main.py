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
from typing import cast

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
offset: int = 982516

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
            session_key = cast(str, skg.get_web_auth_session_key(url))
            _ = SESSION_KEY_FILE.write_text(session_key)
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


def parse(link: str) -> tuple[str, str]:
    """
    Parses a Spotify link to extract the link type and ID.
    Raises ValueError if the link is not a valid Spotify URL.
    """
    if match := re.search(
        r"https://open\.spotify\.com/([a-zA-Z]+)/([a-zA-Z0-9]+)", link
    ):
        return match.group(1), match.group(2)
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
    time_str = time.strftime("%m/%d/%y %H:%M:%S", time.localtime(timestamp))
    print(f"Scrobbled {track} by {artist} at {time_str}")


def get_track_and_scrobble(link_id: str, timestamp: float | None = None) -> int:
    """Gets track information from Spotify and scrobbles it."""
    timestamp = time.time() if timestamp is None else timestamp
    track_info = cast(
        dict[str, object] | None, sp.track(link_id)
    )  # pyright: ignore[reportUnknownMemberType]
    if not track_info:
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

    album_dict = album_info  # pyright: ignore[reportUnknownVariableType]
    album_name = album_dict.get(
        "name"
    )  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    album_artists_info = album_dict.get(
        "artists"
    )  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    first_artist = cast(dict[str, object], artists_info[0])
    artist_name = first_artist.get("name")

    if not (isinstance(album_artists_info, list) and album_artists_info):
        print(f"Track info for {link_id} is missing album artist fields. Skipping.")
        return 0

    first_album_artist = cast(dict[str, object], album_artists_info[0])
    album_artist_name = first_album_artist.get("name")

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
    list_info: dict[str, object] | None,
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
    for item in items:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, dict):
            continue
        item_dict = item  # pyright: ignore[reportUnknownVariableType]
        with suppress(TypeError, KeyError):
            match list_type:
                case "playlist":
                    track_item = item_dict.get(
                        "track"
                    )  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                    if isinstance(track_item, dict):
                        track_dict = (
                            track_item  # pyright: ignore[reportUnknownVariableType]
                        )
                        duration = track_dict.get(
                            "duration_ms"
                        )  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                        if isinstance(duration, int):
                            total_time += duration
                case "album":
                    duration = item_dict.get(
                        "duration_ms"
                    )  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                    if isinstance(duration, int):
                        total_time += duration
                case _:
                    pass

    timestamp -= round(total_time / 1000)

    for item in items:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, dict):
            continue

        item_dict = item  # pyright: ignore[reportUnknownVariableType]
        item_link = None
        with suppress(TypeError, KeyError):
            match list_type:
                case "playlist":
                    track_item = item_dict.get(
                        "track"
                    )  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                    if isinstance(track_item, dict):
                        track_dict = (
                            track_item  # pyright: ignore[reportUnknownVariableType]
                        )
                        external_urls = track_dict.get(
                            "external_urls"
                        )  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                        if isinstance(external_urls, dict):
                            urls_dict = external_urls  # pyright: ignore[reportUnknownVariableType]
                            item_link = urls_dict.get(
                                "spotify"
                            )  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                case "album":
                    external_urls = item_dict.get(
                        "external_urls"
                    )  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                    if isinstance(external_urls, dict):
                        urls_dict = (
                            external_urls  # pyright: ignore[reportUnknownVariableType]
                        )
                        item_link = urls_dict.get(
                            "spotify"
                        )  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                case _:
                    pass

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
                playlist_info = cast(
                    dict[str, object] | None, sp.playlist_items(link_id)
                )  # pyright: ignore[reportUnknownMemberType]
                scrobble_list(playlist_info, "playlist", timestamp)
            case "album":
                album_info = cast(
                    dict[str, object] | None, sp.album_tracks(link_id)
                )  # pyright: ignore[reportUnknownMemberType]
                scrobble_list(album_info, "album", timestamp)
            case "track":
                _ = get_track_and_scrobble(link_id, timestamp)
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
    import pyperclip

    scrobble_queue: queue.Queue[tuple[str, float] | None] = queue.Queue()
    worker_thread = threading.Thread(target=scrobble_worker, args=(scrobble_queue,))
    worker_thread.start()

    print("Enter Spotify links, or type 'paste' to read from your clipboard.")
    print("Type 'q' or 'done' on an empty line to finish.")

    while True:
        try:
            line = input().strip()

            if not line:
                print("Empty submission. Skipping…")

            if line.lower() == "paste":
                clipboard_content = pyperclip.paste()
                links = [
                    link.strip() for link in clipboard_content.split() if link.strip()
                ]
                if not links:
                    print("No links found in the clipboard.")
                else:
                    print(f"Found {len(links)} link(s) in the clipboard. Processing...")
                    for spotify_link in links:
                        scrobble_queue.put((spotify_link, time.time() - offset))
            elif line.lower().strip() in ("stop", "exit", "quit", "q", "end", "done"):
                break
            else:
                for spotify_link in line.split():
                    if spotify_link.strip():
                        scrobble_queue.put((spotify_link.strip(), time.time() - offset))
        except EOFError, KeyboardInterrupt:
            break

    scrobble_queue.put(None)
    worker_thread.join()
    print("All scrobbles have been processed.")
