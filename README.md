# HMB_GLOBAL — slash-only + YouTube Railway fix

This bundle changes the bot to use **Discord slash commands only**.

## Commands
- `$` prefix commands are removed and are no longer registered.
- Help/control messages advertise only `/command`.
- Slash-command registration is enabled by default after deploy.
- Use `/play`, `/search`, `/control`, `/help`, `/join`, `/skip`, `/queue`, etc.

## YouTube / Railway
The previous code forced `mweb`, `web_safari`, and `android_vr` in the extraction path.
The updated code stops forcing that client list and lets the current yt-dlp
YouTube extractor choose its supported clients, while keeping the local bgutil
PO-token provider available.

This directly targets the repeated Railway error:
`Sign in to confirm you're not a bot`.

TikTok extraction is left unchanged.

After replacing the repository files, redeploy Railway and test:
`/play <YouTube link>`

YouTube-side restrictions can still change over time, so no code can guarantee
that every Railway IP will always be accepted.


## Slash-command registration fix

This final bundle also registers the global slash-command tree directly into
every guild when the bot becomes ready. This is intended to fix the situation
where Discord shows **“No commands available here”** after a Railway deploy.

After deploying, check Railway Deploy Logs for:

`Registered <number> guild slash commands`

Then open Discord and type `/` or run `/help`.
