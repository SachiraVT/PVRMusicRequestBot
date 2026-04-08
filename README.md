## PrideVR's Official Music Request Bot 

Basic Music Request Bot used for the PrideVR VRChat Group.

This Bot uses [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper) and [soundevice](https://github.com/spatialaudio/python-sounddevice) to listen for certain trigger phrases and then uses [Spotipy](https://github.com/spotipy-dev/spotipy) to access search on Spotify for the song the individual requests and add it to the [Official PrideVR Playlist](https://open.spotify.com/playlist/5AJkdp9MGIwWLWKyjc71OY?si=a1b899164dce4dae) and to the individual's that is playing the music's queue. It also logs what songs were requested to use for moderation info


### Data you need to Input Yourself

1. You will need to input your own Client ID and Secret from the [Spotify Developer Dashboard](https://developer.spotify.com) to use this 
Input the Details into the appropiate sections in the .env file. (Example Included)

2. You will need to input your own Spotify Playlist ID in the .env file, to find your playlist's ID look for the first set of charcters in the playlists url after spotify.com/playlist/ 
- You don't need the part after si=

3.  You will also need to pick what mic you want the program to use by changing the number on **deviceindex = device_index=6****. To find out what number to use paste this code in the VSCode's terminal and run it once. 
``` 
python -c "import sounddevice as sd; print(sd.query_devices())"
```

4. Lastly, you need to create a file called **SongBlacklist.py** input into the file Songs/Artists you don't want to be allowed to be requested. See below how to format the file
```    
        blacklisted_songs = [
        "Song/Artist 1",
        "Song/Artist 2",
    ]
```

**This code is still heavily WIP but the base part works as intended.**
