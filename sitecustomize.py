"""
HMB_GLOBAL yt-dlp runtime patch.

YouTube currently blocks some Railway/datacenter IPs unless the request
uses a supported client and a Proof-of-Origin token. The bgutil plugin
installed from requirements.txt supplies the token from the local server
started by railpack.json.

This patch deliberately does NOT read, require, or create YouTube cookies.
"""

from __future__ import annotations


def _patch_yt_dlp() -> None:
    try:
        import yt_dlp
    except Exception:
        return

    original_init = yt_dlp.YoutubeDL.__init__
    if getattr(original_init, "_hmb_patched", False):
        return

    def patched_init(self, params=None, *args, **kwargs):
        params = dict(params or {})
        extractor_args = dict(params.get("extractor_args") or {})

        # Preserve the application's existing YouTube options, but make
        # mweb the first client. bgutil's HTTP provider supplies the PO token
        # automatically on port 4416.
        youtube_args = dict(extractor_args.get("youtube") or {})
        configured = youtube_args.get("player_client")

        clients = []
        if configured:
            if isinstance(configured, str):
                configured = [configured]
            for item in configured:
                value = str(item)
                # The existing code passes "default"; it is less useful for
                # the current YouTube bot-check than mweb.
                if value in ("default", "web_safari", "android_vr"):
                    continue
                if value not in clients:
                    clients.append(value)

        for client in ("mweb", "tv", "android_vr"):
            if client not in clients:
                clients.append(client)

        youtube_args["player_client"] = clients
        extractor_args["youtube"] = youtube_args

        # Explicitly point the bgutil plugin at the local provider.
        pot_args = extractor_args.get("youtubepot-bgutilhttp")
        if pot_args is None:
            pot_args = []
        elif isinstance(pot_args, str):
            pot_args = [pot_args]
        else:
            pot_args = list(pot_args)

        if not any(str(x).startswith("base_url=") for x in pot_args):
            pot_args.append("base_url=http://127.0.0.1:4416")
        extractor_args["youtubepot-bgutilhttp"] = pot_args

        params["extractor_args"] = extractor_args
        return original_init(self, params, *args, **kwargs)

    patched_init._hmb_patched = True
    yt_dlp.YoutubeDL.__init__ = patched_init


_patch_yt_dlp()
