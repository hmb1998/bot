# HMB GLOBAL v4 — Music Controls Fix

- Fixed the Queue button on the music control panel: it now opens a real paginated queue.
- Added Queue pagination (previous/next), refresh, and return-to-control buttons.
- Redesigned `/control` with a cleaner two-row music dashboard.
- Added pause/resume, skip, stop, loop, volume modal, search, refresh, and help controls.
- Music button interactions now update the control panel instead of sending many temporary replies.
- Added Discord.js `MessageFlags.Ephemeral` for the music interaction paths to avoid the deprecated `ephemeral` option warning there.
- Improved empty-queue and error handling.
