## PrideVR's Official Music Request Bot 

Basic Music Request Bot used for the PrideVR VRChat Group.

This Bot uses Whisper to listen for certain trigger phrases and then uses Spotipy to access search on Spotify for the song the individual requests and add it to the [Official PrideVR Playlist](https://open.spotify.com/playlist/5AJkdp9MGIwWLWKyjc71OY?si=a1b899164dce4dae) and to the individual's that is playing the music's queue. It also logs what songs were requested to use for moderation info


### Data you need to Input Yourself

1. You will need to input your own Client ID and Secret from the [Spotify Developer Dashboard](https://developer.spotify.com) to use this 
Input the Details into the appropiate sections at the top of the code.

2.  You will also need to pick what mic you want the program to use by changing the **deviceindex**. To find out what number to use paste this code near the top of the code and run it once. 
``` 
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
          print(f"Microphone {index}: {name}")    
```
- After you find you mic's index number and change the device index number (Located where is says **deviceindex = device_index=6**) you can remove the code you pasted above.

3. You also need to create a file called **SongBlacklist.py** input into the file Songs/Artists you don't want to be allowed to be requested. See below how to format the file
```    
        blacklisted_songs = [
        "Song/Artist 1",
        "Song/Artist 2",
    ]
```

4. Lastly, you will need to input your own Spotify Playlist ID, to find your playlist's ID look for the first set of charcters in the playlists url after https://open.spotify.com/playlist/ 
> You don't need the part after si=
**This code is still heavily WIP but the base part works as intended.**
