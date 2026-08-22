"""
HMB_GLOBAL YouTube runtime patch.

This file is loaded automatically by Python before the bot starts.
It adds the bgutil Proof-of-Origin token provider to every yt-dlp
YoutubeDL instance and selects YouTube clients that can work without
browser cookies.

No YouTube cookies or account credentials are stored in the repository.
"""

from __future__ import annotations


def _patch_yt_dlp() -> None:
    try:
        import yt_dlp
    except Exception:
        # During dependency installation yt-dlp may not exist yet.
        return

    original_init = yt_dlp.YoutubeDL.__init__
    if getattr(original_init, "_hmb_no_cookie_patch", False):
        return

    def patched_init(self, params=None, *args, **kwargs):
        params = dict(params or {})

        extractor_args = dict(params.get("extractor_args") or {})

        # Keep the provider namespace separate from the YouTube namespace.
        # This means the existing music.py extractor options remain usable.
        pot_args = list(extractor_args.get("youtubepot-bgutilhttp") or [])
        if not any(str(x).startswith("base_url=") for x in pot_args):
            pot_args.append("base_url=http://127.0.0.1:4416")
        extractor_args["youtubepot-bgutilhttp"] = pot_args

        # The Python API needs the explicit "override" flag to replace the
        # default client preset. mweb + embedded/tv fallbacks avoid the
        # cookie-only web client whenever possible.
        youtube_args = dict(extractor_args.get("youtube") or {})
        youtube_args["player_client"] = [
            "player_client=mweb,web_embedded,tv,tv_simply,android_vr,override"
        ]
        extractor_args["youtube"] = youtube_args

        params["extractor_args"] = extractor_args

        return original_init(self, params, *args, **kwargs)

    patched_init._hmb_no_cookie_patch = True
    yt_dlp.YoutubeDL.__init__ = patched_init


_patch_yt_dlp()
