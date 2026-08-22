# HMB_GLOBAL — YouTube/Spotify no-cookie fix

This patch is for the Railway deployment of `hmb1998/bot`.

## What it changes

- Installs `bgutil-ytdlp-pot-provider` 1.3.1.
- Builds and starts the local POT provider on port 4416.
- Forces yt-dlp to use cookie-free YouTube clients.
- Spotify/spotDL uses the same patched yt-dlp runtime.
- No YouTube cookies need to be added to Railway Variables.

## Files

Replace/add these files in the repository:

1. `requirements.txt`
2. `Dockerfile`
3. `sitecustomize.py`

Then redeploy Railway.

The existing `music.py` can stay in place because `sitecustomize.py` patches every yt-dlp `YoutubeDL` instance at startup.
