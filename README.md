# HMB GLOBAL — Python Port

A Discord bot built and deployed with Python only.

## Main Python modules
- `main.py` — bot startup, events, prefix commands, Railway health server
- `features.py` — utility and configuration slash commands
- `moderation.py` — moderation commands
- `music.py` — voice/music commands

## Runtime
- Python 3.12
- `discord.py`
- `yt-dlp`
- `PyNaCl`
- `Flask`
- FFmpeg

## Railway
Set `TOKEN` in Railway Variables. Optional variables are `OWNER_ID`, `PREFIX`, `REGISTER_COMMANDS`, and `PORT`.

Railway uses `Dockerfile` and starts:

```text
python main.py
```

Health endpoint:

```text
/health
```

There is no Node.js runtime, npm build, discord.js, or Node start command in this version.
