import speech_recognition as sr
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import vrchatosc
from SongBlacklist import blacklisted_songs
from datetime import datetime
import re
from rapidfuzz import fuzz
from dotenv import load_dotenv
load_dotenv()

r = sr.Recognizer()
r.energy_threshold = 3000
r.dynamic_energy_threshold = False
r.pause_threshold = 1.2
r.phrase_threshold = 0.3
osc = vrchatosc.VRChatOSC()
PLAYLIST_ID = os.getenv("TARGET_PLAYLIST_ID")
deviceindex = device_index=6

with sr.Microphone(deviceindex) as source:
    print("Calibrating for ambient noise...")
    r.adjust_for_ambient_noise(source, duration=2)
    print(f"Energy threshold set to: {r.energy_threshold}")

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
            item_id = item.get("item", {}).get("id")
            if item_id == track_id:
                return True

        if len(items) < 100:
            break
        offset += 100

    return False

def handle_song_request():
    SongText = None
    max_retries = 3
    attempts = 0

    while not SongText and attempts < max_retries:
        attempts += 1
        audio = None
        with sr.Microphone(deviceindex) as source:
            audio = r.listen(source)

        try:
            raw = r.recognize_whisper(audio, model="small", initial_prompt="Music request bot. Commands: Music Request, Song Request, Reset, Hey Clanker. Song and artist names")
            result = raw.strip() if raw else ""
            cleaned = re.sub(r'[^\w\s]', '', result).strip()
            print(f"Speech Recognition thinks you said: {result}") # Remove after Testing 

            if cleaned:
                SongText = result
            else:
                print(f"Got empty or junk input, attempt {attempts}/{max_retries}") # Remove after Testing 
                osc.chatbox_input(f"Couldn't hear that, please try again. ({attempts}/{max_retries})", immediate=True)

        except sr.UnknownValueError:
            print(f"Could not understand audio, attempt {attempts}/{max_retries}") # Remove after Testing 
            osc.chatbox_input(f"Couldn't hear that, please try again. ({attempts}/{max_retries})", immediate=True)

    if not SongText:
        osc.chatbox_input("Could not get song name, please ask a Staff Member for Help.", immediate=True)
        return

    results = sp_playlist.search(q=SongText, type="track", limit=1)
    tracks = results["tracks"]["items"]
    if tracks:
        track = tracks[0]
        print(f"Found: {track['name']} by {track['artists'][0]['name']} - Is this Correct?") # Remove after Testing 
        osc.chatbox_input(f"Found: {track['name']} by {track['artists'][0]['name']} - Is this Correct?", immediate=True)

        yes_words = ["yes", "yeah", "yep", "yup", "sure", "correct"]
        no_words = ["no", "nope", "nah", "wrong", "incorrect"]

        confirmation = None
        confirm_attempts = 0
        max_confirm_retries = 3

        while confirm_attempts < max_confirm_retries:
            confirm_attempts += 1
            with sr.Microphone(deviceindex) as source:
                audio = r.listen(source)
            try:
                raw_conf = r.recognize_whisper(audio, model="small", initial_prompt="yes, no, yeah, nope, correct, wrong").lower()
                cleaned_conf = re.sub(r'[^\w\s]', '', raw_conf).strip()

                best_yes = max(fuzz.ratio(cleaned_conf, w) for w in yes_words)
                best_no = max(fuzz.ratio(cleaned_conf, w) for w in no_words)

                if best_yes > 70 or best_no > 70:
                    confirmation = cleaned_conf
                    break
                else:
                    print(f"Couldn't understand response, please try again. ({confirm_attempts}/{max_confirm_retries})") # Remove after Testing 
                    osc.chatbox_input(f"Couldn't understand response, please try again. ({confirm_attempts}/{max_confirm_retries})", immediate=True)

            except sr.UnknownValueError:
                print(f"Couldn't hear that, please try again. ({confirm_attempts}/{max_confirm_retries})") # Remove after Testing 
                osc.chatbox_input(f"Couldn't hear that, please try again. ({confirm_attempts}/{max_confirm_retries})", immediate=True)

        if not confirmation:
            print("Could not get confirmation, please ask a Staff Member for Help.") # Remove after Testing 
            osc.chatbox_input("Could not get confirmation, please ask a Staff Member for Help.", immediate=True)
            return

        best_yes = max(fuzz.ratio(confirmation, w) for w in yes_words)
        best_no = max(fuzz.ratio(confirmation, w) for w in no_words)

        if best_yes > 70:
            track_name = track['name'].replace("\u2019", "'").replace("\u2018", "'")
            artist_name = track['artists'][0]['name']
            full_name = f"{track_name} by {artist_name}"
            normalized_blacklist = [song.replace("\u2019", "'").replace("\u2018", "'").lower() for song in blacklisted_songs]

            if track_name.lower() in normalized_blacklist or artist_name.lower() in normalized_blacklist or full_name.lower() in normalized_blacklist:
                print("This Song/Artist is not Allowed to be Added to Playlist") # Remove after Testing 
                osc.chatbox_input("This Song/Artist is not Allowed to be Added to Playlist")
                log_song_request(track_name, artist_name, "Blocked")
            elif is_track_in_playlist(track['id'], "PLAYLIST_ID"):
                print("Song is already in the Playlist") # Remove after Testing 
                osc.chatbox_input("That song is already in the Playlist!", immediate=True)
                log_song_request(track_name, artist_name, "Duplicate")
            else:
                try:
                    sp_playback.add_to_queue(track['id'])
                    print("Song added to queue on playback account")
                except Exception as e:
                    print(f"Could not add to queue (no active device): {e}")

                sp_playlist.playlist_add_items(playlist_id=PLAYLIST_ID, items=[track['uri']])
                print("Song was added to Playlist")
                osc.chatbox_input("This Song was added to the Playlist", immediate=True)
                log_song_request(track_name, artist_name, "Added")

        elif best_no > 70:
            print("Song was not able to be added to Playlist, Ask a Staff Member for Help")
            osc.chatbox_input("Song was not able to be added to Playlist, Ask a Staff Member for Help")
            log_song_request(track['name'], track['artists'][0]['name'], "Failed")
        else:
            osc.chatbox_input("Can you Speak Up?", immediate=True)
    else:
        osc.chatbox_input("No tracks found.", immediate=True)


def listen_for_trigger():
    trigger_phrases = ["song request", "music request", "request song", "play a song", "add a song"]

    while True:
        print("Listening...")

        try:
            with sr.Microphone(deviceindex) as source:
                audio = r.listen(source)

            recognized_text = r.recognize_whisper(audio, model="small", initial_prompt="song request, music request, request song, play a song, add a song").lower()
            recognized_text = re.sub(r'[^\w\s]', '', recognized_text).strip()
            print("Speech Recognition thinks you said " + recognized_text)

            exact_match = any(phrase in recognized_text for phrase in trigger_phrases)
            fuzzy_match = any(fuzz.partial_ratio(phrase, recognized_text) > 80 for phrase in trigger_phrases)

            if exact_match or fuzzy_match:
                print("Listening for Song Request") # Remove after Testing 
                osc.chatbox_input("Listening for Song Request", immediate=True)
                handle_song_request()

        except sr.UnknownValueError:
            print("Could not understand audio, listening again...") # Remove after Testing 
        except sr.RequestError as e:
            print(f"Could not request results; {e}") # Remove after Testing 
            break


listen_for_trigger()

# TO DO by Priorty
# If Gets Wrong Song and is told No then recommend the next song on search list
# Try to get make it so I won't hear the instance from the bot but the code picks it up
# Make Way for Song to Be added to Blacklist after 3 votes but with a force way for staff
# If told Hey  Clanker say I have feelings too you know
# Make Play Hamburger Sound if Given a key word