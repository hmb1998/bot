# HMB GLOBAL — Python Only

This edition contains the Discord bot runtime and command implementations in Python.
There is no Node.js, npm, discord.js, HTML, or JSON command/config source.

## Run
Set `TOKEN` in Railway Variables, then start with:

```text
python main.py
```

Optional variables: `OWNER_ID`, `PREFIX` (default `$`), `REGISTER_COMMANDS` (default `true`), `PORT`.

The bot stores settings, warnings, and XP in `hmb.sqlite3` using Python's built-in `sqlite3`.
FFmpeg is required for music playback and is installed by the included Dockerfile.

## Commands
Moderation, anti-spam/link protection, tickets, warnings, XP/rank, polls, giveaways, music,
server/user tools, and utility commands are implemented in Python modules.
