HMB GLOBAL — Duplicate Slash Command Fix

Problem:
Discord was crashing with:
discord.app_commands.errors.CommandAlreadyRegistered:
Command 'remove' already registered.

Actual cause found in the supplied repository:
- music.py registers /remove for removing an item from the music queue.
- extras.py also registered /remove for removing a member from a ticket.
Both commands used the same slash-command name, so discord.py rejected the second
registration during startup.

Fix applied:
- Kept music.py /remove unchanged: it removes a song from the queue.
- Renamed the ticket-member command in extras.py from /remove to /ticket-remove.
- The Python function was renamed to ticket_remove.
- The existing setup guard in extras.py is preserved.

Verification:
A scan of all supplied Python files found no other duplicate @bot.tree.command names.

Install:
1. Replace the repository files with the files in this ZIP (or at minimum replace
   extras.py and keep the other files unchanged).
2. Commit and push to GitHub.
3. Railway will redeploy.
4. Check Deploy Logs. The CommandAlreadyRegistered: Command 'remove' error should
   no longer occur.

Result:
- /remove = remove a song from the music queue
- $remove = same command through the existing prefix adapter
- /ticket-remove = remove a member from a ticket
- $ticket-remove = same ticket command through the prefix adapter
