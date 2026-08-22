# HMB GLOBAL — Dual Command + Control Center Upgrade

## Commands
Every registered Python slash command is exposed in both forms:

- `/play``
- `/skip``
- `/volume``
- `/control``
- `/help``
- All moderation/features commands use the same pattern.

The bot presence shows: `/help | HMB GLOBAL`.

## Control Center
Run `/control` to open the interactive panel. It includes:

- Pause / Resume / Skip / Stop / Queue
- Volume 25% / 50% / 75% / 100%
- Loop toggle
- Anti-Spam toggle
- Link Guard toggle
- Live status

Administrator-only security buttons are permission checked.

## Anti-Spam
When Anti-Spam is ON, protection is layered:

1. Existing burst limiter: 5 messages in 7 seconds.
2. Escalation timeout after a stronger burst when the bot has Moderate Members permission.
3. Duplicate-message detection.
4. Mention/role-mention flood detection.
5. Very-long message flood detection.
6. Cooldown to avoid repeated warning spam.

## Music links
The music resolver accepts normal `yt-dlp` URLs/searches and TikTok URLs through yt-dlp's `url` operation, which resolves TikTok items to user-friendly source URLs before streaming.

TikTok playlists can therefore be queued as multiple tracks. TikTok/other supported `yt-dlp` URLs are passed through the normal extractor.

## Railway
The code now defaults `REGISTER_COMMANDS=true`, so slash commands can register after deploy.

Your Railway Variables should contain:

- `TOKEN` = your Discord bot token
- `OWNER_ID` = your Discord user ID
- `REGISTER_COMMANDS` = `true`

If Discord global slash commands were previously rate-limited, wait for the limit to clear and then redeploy once. After commands are registered, you can set `REGISTER_COMMANDS=false` to avoid repeated global syncs.

## Discord Developer Portal
Make sure the bot has these intents enabled:

- Message Content Intent
- Server Members Intent
- Voice State Intent

For moderation/anti-spam timeout actions, the bot also needs the required Discord server permissions and its role must be above members it moderates.

## Bot profile
Discord's bot profile/bio text is normally edited in the Discord Developer Portal; the code cannot reliably rewrite the application profile description using a normal bot token. A suitable profile line is:

`HMB GLOBAL 🤖 | Commands: /help | Music 🎵 | Anti-Spam 🛡️ | Control Center 🎛️`
