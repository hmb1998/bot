HMB GLOBAL — Duplicate Slash Command Fix

Based on hmb1998/bot main branch.

Problem fixed:
discord.app_commands.errors.CommandAlreadyRegistered:
Command 'remove' already registered.

Cause:
setup_extra_commands() was being reached more than once, so discord.py attempted
to register the same slash commands a second time.

Fix:
extras.py now marks the bot after the first setup and returns safely if setup is
called again. Existing commands, including /remove, are preserved.

Install:
1. In GitHub open extras.py.
2. Replace its contents with the extras.py in this ZIP.
3. Commit the change.
4. Railway will redeploy automatically.
5. Check Deploy Logs. The duplicate 'remove' registration crash should be gone.

Note:
This ZIP contains the corrected extras.py and instructions only; the other
repository files are unchanged.
