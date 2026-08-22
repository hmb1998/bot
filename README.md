# HMB_GLOBAL — final no-cookie YouTube/Spotify fix

The Railway logs show the remaining failure is YouTube's datacenter bot check:
`Sign in to confirm you're not a bot`.

The previous deployment did not actually run the bgutil POT server, and the
current `music.py` still selects `default/web_safari/android_vr`. This bundle
fixes the deployment layer without requiring `YOUTUBE_COOKIES_B64`.

## Upload/replace these 3 files in the repo

- `requirements.txt`
- `railpack.json`
- `sitecustomize.py`

Then redeploy Railway.

### What happens after deploy

Railpack installs Python 3.12 + Node 22, builds the bgutil provider, installs
the Python yt-dlp plugin, starts the provider on `127.0.0.1:4416`, and only
then starts `python main.py`.

`sitecustomize.py` changes yt-dlp's clients to start with `mweb` and connects
the bgutil provider automatically.

Do NOT add `YOUTUBE_COOKIES_B64` for this fix.

The provider is not a guaranteed bypass for every YouTube block, but it is the
current recommended approach in yt-dlp's PO-token guide for clients requiring
PO tokens.
