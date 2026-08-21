# HMB GLOBAL — Python Edition

HMB GLOBAL is a Discord bot running entirely on Python.

## Runtime
- Python 3.12
- discord.py 2.5+
- yt-dlp for music extraction
- FFmpeg for voice playback
- Flask for Railway health checks

## Railway
Required variable:
- `TOKEN` — Discord bot token

Optional:
- `OWNER_ID`
- `PREFIX` (default `$`)
- `REGISTER_COMMANDS` (default `true`)
- `PORT` (Railway supplies it automatically)

### Build
Railway uses the included `Dockerfile`.

### Start
```text
python main.py
```

### Health check
```text
/health
```

Do not add `python main.py` as a Pre-deploy command. The service starts it through the Dockerfile/Railway configuration.
