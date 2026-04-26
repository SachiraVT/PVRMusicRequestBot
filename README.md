## PrideVR's Official Music Request Bot - Public Release

Basic Music Request Bot used for the [PrideVR VRChat Group](https://vrchat.com/home/group/grp_548b8449-2fc6-48b8-bbdf-b380401d9b66).

This Bot uses [Discord.py](https://github.com/Rapptz/discord.py) to listen for certain trigger phrases and then uses [Spotipy](https://github.com/spotipy-dev/spotipy) and [YTMusicAPI](https://github.com/sigma67/ytmusicapi) to access and search on Spotify/YTMusic for the song the individual requests and add it to a playlist as well as to the individual's that is playing the music's queue. It also logs what songs were requested to use for moderation info


### Data you need to Input Yourself in .env File 
*Example File is Included*

1. You will need to input your own Client ID(s) and Secret(s) from the [Spotify Developer Dashboard](https://developer.spotify.com) Input the Details into the appropiate sections  

2. You will need to input your own Spotify Playlist ID, to find your playlist's ID look for the first set of charcters in the playlists url after spotify.com/playlist/ 
- You don't need the part after si=

3.  You will also need to grab the bot token from the [Discord Devolper Portal](https://discord.com/developers/home) and input the in file along side the other discord related stuff 

### Other Data that Needs to be Created
You need to also create a file called **SongBlacklist.py**, input into the file Songs/Artists you don't want to be allowed to be requested. See below for how to format the file
```    
        blacklisted_songs = [
        "Song/Artist 1",
        "Song/Artist 2",
    ]
```
### TLDR Notice

This version of the Code won't have all the features that the one that is used in [PrideVR](https://vrchat.com/home/group/grp_548b8449-2fc6-48b8-bbdf-b380401d9b66) Instances will have. But it will have the basic features
