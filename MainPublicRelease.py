import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from pythonosc import udp_client
from SongBlacklist import blacklisted_songs
from datetime import datetime
import re
from rapidfuzz import fuzz
from dotenv import load_dotenv
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel

load_dotenv()

model = WhisperModel("small", device="cpu", compute_type="int8")

SAMPLE_RATE = 16000
RECORD_SECONDS = 5
DEVICE_INDEX = 6

client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
PLAYLIST_ID = os.getenv("TARGET_PLAYLIST_ID")

sp_playlist = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_PLAYLIST_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_PLAYLIST_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="playlist-modify-public playlist-modify-private",
    cache_path=".cache-playlist"
))

sp_playback = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_PLAYBACK_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_PLAYBACK_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-modify-playback-state user-read-playback-state",
    cache_path=".cache-playback"
))

def listen(initial_prompt=""):
    audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=DEVICE_INDEX
    )
    sd.wait()
 
    segments, _ = model.transcribe(
        audio.flatten(),
        language="en",
        beam_size=1,
        initial_prompt=initial_prompt
    )
    text = " ".join(seg.text for seg in segments).strip().lower()
    return re.sub(r'[^\w\s]', '', text).strip()


def log_song_request(song_name, artist_name, status):
    with open("song_requests.txt", "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {song_name} by {artist_name} - {status}\n")


def is_track_in_playlist(track_id, playlist_id):
    offset = 0
    while True:
        results = sp_playlist.playlist_items(playlist_id=PLAYLIST_ID, limit=100, offset=offset)
        items = results["items"]

        if not items:
            break

        for item in items:
            item_id = item.get("track", {}).get("id")
            if item_id == track_id:
                return True

        if len(items) < 100:
            break
        offset += 100

    return False

def handle_song_request():
    song_prompt = "Music request bot. Commands: Music Request, Song Request, Reset, Hey Clanker. Song and artist names"
    confirm_prompt = "yes, no, yeah, nope, correct, wrong"
    yes_words = ["yes", "yeah", "yep", "yup", "sure", "correct"]
    no_words  = ["no", "nope", "nah", "wrong", "incorrect"]

    SongText = None
    for attempt in range(1, 4):
        text = listen(initial_prompt=song_prompt)
        print(f"Speech Recognition thinks you said: {text}")  # Debug Line, Remove is Wanted
        if text:
            SongText = text
            break
        else:
            print(f"Got empty or junk input, attempt {attempt}/3") # Debug Line, Remove is Wanted
            client.send_message("/chatbox/input", [f"Couldn't hear that, please try again. ({attempt}/{3})", True])


    if not SongText:
        client.send_message("/chatbox/input", [f"Could not get song name, please ask a Staff Member for Help.", True])
        return

    results = sp_playlist.search(q=SongText, type="track", limit=1)
    tracks = results["tracks"]["items"]

    if not tracks:
        client.send_message("/chatbox/input", [f"No tracks found.", True])
        return

    track = tracks[0]
    print(f"Found: {track['name']} by {track['artists'][0]['name']} - Is this Correct?") # Debug Line, Remove is Wanted 
    client.send_message("/chatbox/input", [f"Found: {track['name']} by {track['artists'][0]['name']} - Is this Correct?", True])

    confirmation = None
    for confirm_attempt in range(1, 4):
        conf_text = listen(initial_prompt=confirm_prompt)
 
        best_yes = max(fuzz.ratio(conf_text, w) for w in yes_words)
        best_no  = max(fuzz.ratio(conf_text, w) for w in no_words)
 
        if best_yes > 70 or best_no > 70:
            confirmation = conf_text
            break
        else:
            print(f"Couldn't understand response, attempt {confirm_attempt}/3")  # Debug Line, Remove is Wanted
            client.send_message("/chatbox/input", [f"Couldn't understand response, please try again. ({confirm_attempt}/3)", True])
 
    if not confirmation:
        print("Could not get confirmation, please ask a Staff Member for Help.")  # Debug Line, Remove is Wanted
        client.send_message("/chatbox/input", [f"Could not get confirmation, please ask a Staff Member for Help.", True])
        return
 
    best_yes = max(fuzz.ratio(confirmation, w) for w in yes_words)
    best_no  = max(fuzz.ratio(confirmation, w) for w in no_words)
 
    if best_yes > 70:
        track_name  = track['name'].replace("\u2019", "'").replace("\u2018", "'")
        artist_name = track['artists'][0]['name']
        full_name   = f"{track_name} by {artist_name}"
        normalized_blacklist = [
            song.replace("\u2019", "'").replace("\u2018", "'").lower()
            for song in blacklisted_songs
        ]
 
        if (track_name.lower() in normalized_blacklist
                or artist_name.lower() in normalized_blacklist
                or full_name.lower() in normalized_blacklist):
            print("This Song/Artist is not Allowed to be Added to Playlist")  # Debug Line, Remove is Wanted
            client.send_message("/chatbox/input", [f"This Song/Artist is not Allowed to be Added to Playlist", True])
            log_song_request(track_name, artist_name, "Blocked")
 
        elif is_track_in_playlist(track['id'], PLAYLIST_ID):
            print("Song is already in the Playlist")  # Debug Line, Remove is Wanted
            client.send_message("/chatbox/input", [f"That song is already in the Playlist!", True])
            log_song_request(track_name, artist_name, "Duplicate")
 
        else:
            try:
                sp_playback.add_to_queue(track['id'])
                print("Song added to queue on playback account")  # Debug Line, Remove is Wanted
            except Exception as e:
                print(f"Could not add to queue (no active device): {e}")
 
            sp_playlist.playlist_add_items(playlist_id=PLAYLIST_ID, items=[track['uri']])
            print("Song was added to Playlist")  # Debug Line, Remove is Wanted
            client.send_message("/chatbox/input", [f"This Song was added to the Playlist", True])
            log_song_request(track_name, artist_name, "Added")
 
    elif best_no > 70:
        print("Song was not able to be added to Playlist, Ask a Staff Member for Help")  # Debug Line, Remove is Wanted
        client.send_message("/chatbox/input", [f"Song was not able to be added to Playlist, Ask a Staff Member for Help", True])
        log_song_request(track['name'], track['artists'][0]['name'], "Failed")
 
    else:
        client.send_message("/chatbox/input", [f"Can you Speak Up?", True])
    
def listen_for_trigger():
    trigger_phrases = ["song request", "music request", "request song", "play a song", "add a song"]
    trigger_prompt  = "song request, music request, request song, play a song, add a song"
 
    while True:
        print("Listening...")
        text = listen(initial_prompt=trigger_prompt)
 
        if not text:
            continue
 
        print("Speech Recognition thinks you said " + text)  # Debug Line, Remove is Wanted
 
        exact_match = any(phrase in text for phrase in trigger_phrases)
        fuzzy_match = any(fuzz.partial_ratio(phrase, text) > 80 for phrase in trigger_phrases)
 
        if exact_match or fuzzy_match:
            print("Listening for Song Request")  # Debug Line, Remove is Wanted
            client.send_message("/chatbox/input", [f"Listening for Song Request", True])
            handle_song_request()

listen_for_trigger()
