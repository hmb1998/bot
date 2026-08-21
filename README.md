# HMB GLOBAL — Python Only

This edition contains the Discord bot runtime and command implementations in Python.
There is no Node.js, npm, discord.js, HTML, or JSON command/config source.

## Run
Set `TOKEN` in Railway Variables, then start with:

```text
python main.py
```

Optional variables: `OWNER_ID`, `PREFIX` (default `$`), `REGISTER_COMMANDS` (default `false`), `PORT`.

`REGISTER_COMMANDS=false` avoids Discord global-command rate limits during frequent Railway restarts. Use the `$refresh` command (administrator) to copy/sync all slash commands to the current server, or set `REGISTER_COMMANDS=true` only when you specifically need a global sync.

The bot stores settings, warnings, and XP in `hmb.sqlite3` using Python's built-in `sqlite3`.
FFmpeg, PyNaCl, and davey are required for music/voice playback and are installed by the included Dockerfile and requirements.

## Commands
Moderation, anti-spam/link protection, tickets, warnings, XP/rank, polls, giveaways, music,
server/user tools, and utility commands are implemented in Python modules.


## Slash + Prefix control
- Slash commands use `/command`.
- Prefix aliases use `$command` (or the value of `PREFIX`).
- `REGISTER_COMMANDS=false` is the safe Railway default and prevents global sync on every restart.
- After the bot is online, run `$sync` once in your Discord server as an Administrator. This registers the slash commands to that server immediately.
- `$syncglobal` is OWNER_ID-only and should only be used when a global sync is actually needed.
- Music supports YouTube, Spotify (resolved through spotDL), TikTok/other yt-dlp-supported URLs, queue controls, shuffle, skip, volume, loop, now playing, and clear/remove queue.
- Anti-spam is enabled by default for new servers; administrators can use `/antispam` or `$antispam` to change it.
