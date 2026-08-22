# HMB GLOBAL music fix

- `/play` supports YouTube URLs/search and Spotify URLs.
- Spotify extraction now forces spotDL's official Spotify Web API path instead of the failing SpotAPIFree session path.
- No YouTube cookie is required by this code. Cookies remain optional if YouTube later asks for authentication.
- `asyncio` is explicitly imported in `music.py`.

## Railway variables for Spotify

Set these only if Spotify still rejects the default credentials:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`

Do not put these secrets in GitHub files.

After uploading/deploying, restart the Railway service.
