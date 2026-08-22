# HMB GLOBAL music fix

- `/play` supports YouTube URLs/search and TikTok URLs.
- TikTok extraction now forces yt-dlp's official TikTok Web API path instead of the failing SpotAPIFree session path.
- No YouTube cookie is required by this code. Cookies remain optional if YouTube later asks for authentication.
- `asyncio` is explicitly imported in `music.py`.

## Railway variables for TikTok

Set these only if TikTok still rejects the default credentials:

- `YOUTUBE_COOKIES_B64`
- `YOUTUBE_COOKIES_B64`

Do not put these secrets in GitHub files.

After uploading/deploying, restart the Railway service.
