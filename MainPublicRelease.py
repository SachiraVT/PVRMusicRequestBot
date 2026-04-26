import os
import json
import re
import discord
import time
import asyncio
import sys
sys.stdout.reconfigure(encoding="utf-8")
from discord import app_commands
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pythonosc import udp_client
from datetime import datetime
from dotenv import load_dotenv
import logging
logging.getLogger("spotipy").setLevel(logging.CRITICAL)

try:
    from ytmusicapi import YTMusic
    ytmusic = YTMusic()
    YT_AVAILABLE = True
except ImportError:
    YT_AVAILABLE = False

try:
    from SongBlacklist import blacklisted_songs
except ImportError:
    blacklisted_songs = []

load_dotenv()

OSC_HOST            = os.getenv("OSC_HOST", "127.0.0.1")
OSC_PORT            = int(os.getenv("OSC_PORT", 9002))
OSC_RESEND_INTERVAL = int(os.getenv("OSC_RESEND_INTERVAL", 3))
OSC_ENABLED = os.getenv("OSC_ENABLED", "true").lower() == "true"
LOG_FILENAME = f"logs/debug/debug_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
STATS_FILE = "stats.json"


osc_client = udp_client.SimpleUDPClient(OSC_HOST, OSC_PORT)

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

sp_playlist_read = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_PLAYBACK_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_PLAYBACK_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-modify-playback-state user-read-playback-state playlist-read-private playlist-read-collaborative",
    cache_path=".cache-playlist-read"
))

now_playing: dict | None = None

def log_debug(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    with open(LOG_FILENAME, "a", encoding="utf-8") as f:
        f.write(line)

def log_song_request(song_name, artist_name, status):
    with open("logs/song_requests.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {song_name} by {artist_name} - {status}\n")

def is_track_in_playlist(track_id, playlist_id=PLAYLIST_ID):
    offset = 0
    while True:
        results = sp_playlist_read.playlist_items(playlist_id=playlist_id, limit=100, offset=offset)
        items = results["items"]

        if not items:
            break

        for item in items:
            track = item.get("track")
            if track is None:
                continue
            item_id = track.get("id")
            if item_id is None:
                continue 
            if item_id == track_id:
                return True

        if len(items) < 100:
            break
        offset += 100
    return False

def extract_spotify_id(url: str) -> str | None:
    match = re.search(r"spotify\.com/track/([A-Za-z0-9]+)", url)
    return match.group(1) if match else None

def extract_yt_video_id(url: str) -> str | None:
    match = re.search(r"(?:v=|youtu\.be/|music\.youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None

def resolve_track(link: str) -> dict | None:
    spotify_id = extract_spotify_id(link)
    if spotify_id:
        try:
            return sp_playlist.track(spotify_id)
        except Exception:
            return None
 
    yt_id = extract_yt_video_id(link)
    if yt_id and YT_AVAILABLE:
        try:
            info    = ytmusic.get_song(yt_id)
            title   = info["videoDetails"]["title"]
            artist  = info["videoDetails"]["author"]
            results = sp_playlist.search(q=f"{title} {artist}", type="track", limit=1)
            tracks  = results["tracks"]["items"]
            return tracks[0] if tracks else None
        except Exception:
            return None
 
    return None

def is_blacklisted(track: dict) -> bool:
    track_name  = track["name"].replace("\u2019", "'").replace("\u2018", "'")
    artist_name = track["artists"][0]["name"]
    full_name   = f"{track_name} by {artist_name}"
    normalized  = [s.replace("\u2019", "'").replace("\u2018", "'").lower() for s in blacklisted_songs]
    return (
        track_name.lower()  in normalized
        or artist_name.lower() in normalized
        or full_name.lower()  in normalized
    )

def get_stats() -> dict:
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}

def increment_stat(key: str) -> int:
    stats = get_stats()
    stats[key] = stats.get(key, 0) + 1
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    return int(stats[key])

async def osc_now_playing_loop():
    global now_playing
    last_track_id   = None
    current_message = None
    last_sent       = 0.0
 
    while True:
        try:
            current = None
            for attempt in range(3):
                try:
                    current = await asyncio.wait_for(
                        asyncio.to_thread(sp_playback.currently_playing, market="US"),
                        timeout=5.0
                    )
                    break
                except asyncio.TimeoutError:
                    log_debug(f"[OSC loop] Spotify call timed out (attempt {attempt + 1})")
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2)
                except Exception as e:
                    log_debug(f"[OSC loop] Spotify call failed (attempt {attempt + 1}): {e}")
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2)

            if current and current.get("is_playing"):
                track    = current["item"]
                track_id = track["id"]

                if track_id != last_track_id:
                    title           = track["name"]
                    artist          = ", ".join(a["name"] for a in track["artists"])
                    current_message = f"Now Playing: {title} by {artist}"
                    last_track_id   = track_id
                    now_playing     = {"title": title, "artist": artist, "message": current_message}
                    print(current_message)
            else:
                now_playing = None

            now = time.time()
            if OSC_ENABLED and current_message and (now - last_sent) >= OSC_RESEND_INTERVAL:
                try:
                    osc_client.send_message("/chatbox/input", [current_message, True])
                    last_sent = now
                except Exception as e:
                    log_debug(f"[OSC loop] Error sending OSC message: {e}")

        except asyncio.TimeoutError:
            log_debug("[OSC loop] Spotify call timed out after 3 attempts, skipping cycle")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            log_debug(f"[OSC loop] Error after 3 attempts: {e}, retrying in 10s...")
            print(f"[OSC loop] Error after 3 attempts: {e}, retrying in 10s...")
            await asyncio.sleep(10)
            continue

        await asyncio.sleep(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, reconnect=True)
 

#Bot Startup
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} — slash commands synced.")
    log_debug(f"[BOT] Logged in as {bot.user} — slash commands synced.")
    bot.loop.create_task(osc_now_playing_loop())
    print("OSC Started.")
    log_debug("[BOT] OSC loop started.")

#Bot Error Handler
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log_debug(f"[ERROR] {interaction.command.name if interaction.command else 'unknown'} — {error}")
    try:
        await interaction.response.send_message("Somthing went wrong. Please try again later.", ephemeral=True)
    except:
        try:
            await interaction.followup.send("Somthing went wrong. Please try again later.", ephemeral=True)
        except:
            pass

#Song Request Command
@bot.tree.command(name="songrequest", description="Request a song via a Spotify or YouTube Music link.")
@app_commands.describe(link="Paste a Spotify track link or YouTube Music link")
async def songrequest(interaction: discord.Interaction, link: str):
    if interaction.channel_id != int(os.getenv("SONG_REQUEST_CHANNEL_ID")):
        log_debug(f"[SONGREQ] Wrong channel attempt by {interaction.user} ({interaction.user.id}) in #{interaction.channel.name} ({interaction.channel_id})")
        await interaction.response.send_message(
           f"Song requests can only be subbmited in <#{os.getenv('SONG_REQUEST_CHANNEL_ID')}>.",
            ephemeral=True
        )
        return 
    user_tag = f"{interaction.user} ({interaction.user.id})"
    print(f"[SONGREQ] Request from {user_tag} — link: {link}")
    log_debug(f"[SONGREQ] Request from {user_tag} — link: {link}")
    
    try:
        await interaction.response.defer(thinking=True)
        log_debug(f"[SONGREQ] Deferred OK")
    except Exception as e:
        log_debug(f"[SONGREQ] FAILED to defer: {e}")
        return
    try:
        track = await asyncio.to_thread(resolve_track, link)
        log_debug(f"[SONGREQ] resolve_track result: {track['name'] if track else None}")
    except Exception as e:
        log_debug(f"[SONGREQ] EXCEPTION in resolve_track: {e}")
        await interaction.followup.send("An error occurred while looking up the track.", ephemeral=True)
        return
    
    if not track:
        log_debug(f"[SONGREQ] No track found for link: {link}")
        await interaction.followup.send(
            "Couldn't find that track on Spotify or YT Music. Make sure you're sending a valid link.",
            ephemeral=True
        )
        return
 
    track_name  = track["name"].replace("\u2019", "'").replace("\u2018", "'")
    artist_name = track["artists"][0]["name"]
    full_name   = f"**{track_name}** by **{artist_name}**"
    log_debug(f"[SONGREQ] Track resolved: {track_name} by {artist_name}")
 
    try:
        blacklisted = is_blacklisted(track)
        log_debug(f"[SONGREQ] Blacklist check: {blacklisted}")
    except Exception as e:
        log_debug(f"[SONGREQ] EXCEPTION in is_blacklisted: {e}")
        await interaction.followup.send("An error occurred checking the blacklist.", ephemeral=True)
        return
    
    if blacklisted:
        log_song_request(track_name, artist_name, "Blocked")
        await interaction.followup.send(
            f"{full_name} is not allowed to be added to the playlist.",
            ephemeral=True
        )
    
    already_in = None
    for attempt in range(3):
        try:
            already_in = await asyncio.wait_for(
                asyncio.to_thread(is_track_in_playlist, track["id"]),
                timeout=15.0
            )
            log_debug(f"[SONGREQ] Playlist duplicate check: {already_in}")
            break
        except asyncio.TimeoutError:
            log_debug(f"[SONGREQ] TIMEOUT in is_track_in_playlist (attempt {attempt + 1})")
            if attempt == 2:
                await interaction.followup.send("Spotify took too long to respond. Try again.", ephemeral=True)
                return
            await asyncio.sleep(2)
        except Exception as e:
            log_debug(f"[SONGREQ] EXCEPTION in is_track_in_playlist (attempt {attempt + 1}): {e}")
            if attempt == 2:
                await interaction.followup.send("An error occurred checking the playlist.", ephemeral=True)
                return
            await asyncio.sleep(2)


    if already_in:
        log_song_request(track_name, artist_name, "Duplicate")
        await interaction.followup.send(f"{full_name} is already in the playlist!", ephemeral=True)
        return

    try:
        await asyncio.wait_for(
            asyncio.to_thread(sp_playlist.playlist_add_items, PLAYLIST_ID, [track["uri"]]),
            timeout=10.0
        )
        log_debug(f"[SONGREQ] Added to playlist OK")
    except asyncio.TimeoutError:
        log_debug(f"[SONGREQ] TIMEOUT adding to playlist")
        await interaction.followup.send("Spotify took too long to respond. Try again.", ephemeral=True)
        return
    except Exception as e:
        log_debug(f"[SONGREQ] EXCEPTION adding to playlist: {e}")
        await interaction.followup.send("An error occurred adding the song to the playlist.", ephemeral=True)
        return

    log_song_request(track_name, artist_name, "Added")

    try:
        await asyncio.wait_for(
            asyncio.to_thread(sp_playback.add_to_queue, track["uri"]),
            timeout=10.0
        )
        log_debug(f"[SONGREQ] Added to queue OK")
    except asyncio.TimeoutError:
        log_debug(f"[SONGREQ] Queue add timed out (non-fatal)")
    except Exception as e:
        log_debug(f"[SONGREQ] Couldn't add to queue (non-fatal): {e}")

    try:
        embed = discord.Embed(
            title="Song Added!",
            description=full_name,
            color=discord.Color.green()
        )
        if track["album"]["images"]:
            embed.set_thumbnail(url=track["album"]["images"][0]["url"])
        embed.add_field(name="Album", value=track["album"]["name"], inline=True)
        minutes, seconds = divmod(track["duration_ms"] // 1000, 60)
        embed.add_field(name="Duration", value=f"{minutes}:{seconds:02d}", inline=True)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)
        log_debug(f"[SONGREQ] Response sent OK — {track_name} by {artist_name}")
    except Exception as e:
        log_debug(f"[SONGREQ] EXCEPTION sending followup embed: {e}")

# Reconnect Discord Bot if it Disconnects
async def main():
    while True:
        try:
            await bot.start(os.getenv("DISCORD_BOT_TOKEN"))
        except discord.errors.ConnectionClosed as e:
            log_debug(f"[BOT] Connection closed: {e}. Reconnecting in 5s...")
            print(f"[BOT] Connection closed: {e}. Reconnecting in 5s...")
        except discord.errors.GatewayNotFound:
            log_debug("[BOT] Gateway not found. Reconnecting in 10s...")
            print("[BOT] Gateway not found. Reconnecting in 10s...")
            await asyncio.sleep(10)
        except Exception as e:
            log_debug(f"[BOT] Unexpected error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)
        finally:
            if not bot.is_closed():
                await bot.close()

if __name__ == "__main__":
    asyncio.run(main())