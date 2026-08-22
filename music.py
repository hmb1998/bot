import asyncio
import base64
import logging
import os
import random
import re
import tempfile
from collections import deque

import discord
from discord import app_commands
import yt_dlp


LOG = logging.getLogger("HMB_GLOBAL")

YOUTUBE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)

YDL_OPTS = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": False,
    "default_search": "ytsearch1",
    "extract_flat": False,
    "socket_timeout": 20,
    "retries": 2,
    "fragment_retries": 2,
    "http_headers": {"User-Agent": YOUTUBE_UA},
    "js_runtimes": {"node": {}},
}

FFMPEG_OPTS = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-nostdin"
    ),
    "options": "-vn",
}


def _cookie_file_from_env():
    path = os.getenv("YOUTUBE_COOKIES_FILE", "").strip()
    if path and os.path.isfile(path):
        return path

    encoded = os.getenv("YOUTUBE_COOKIES_B64", "").strip()
    raw = os.getenv("YOUTUBE_COOKIES", "")
    if not encoded and not raw:
        return None

    try:
        data = base64.b64decode(encoded).decode("utf-8") if encoded else raw
    except Exception as exc:
        LOG.warning("Invalid YOUTUBE_COOKIES_B64: %s", exc)
        return None

    fd, path = tempfile.mkstemp(prefix="hmb-youtube-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data)
    return path


def _youtube_opts(cookie_file=None, client=None):
    opts = dict(YDL_OPTS)
    opts["http_headers"] = dict(YDL_OPTS["http_headers"])

    clients = [client] if client else ["mweb", "web_safari", "android_vr"]
    opts["extractor_args"] = {
        "youtube": {
            "player_client": clients,
        },
        "youtubepot-bgutilhttp": {
            "base_url": os.getenv("BGUTIL_POT_URL", "http://127.0.0.1:4416"),
        },
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


def _generic_opts(cookie_file=None):
    opts = dict(YDL_OPTS)
    opts["http_headers"] = dict(YDL_OPTS["http_headers"])
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


class Track:
    def __init__(self, title, url, webpage=None):
        self.title = title
        self.url = url
        self.webpage = webpage or url


class MusicManager:
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.current = {}
        self.voice = {}
        self.loop = {}
        self.volume = {}
        self.skip_once = set()

    async def extract(self, query):
        loop = asyncio.get_running_loop()
        query_text = str(query or "").strip()
        if not query_text:
            raise RuntimeError("تکایە ناوی گۆرانی یان لینکێک بنووسە.")
        return await loop.run_in_executor(None, self._extract_sync, query_text)

    def _extract_sync(self, query_text):
        cookie_file = _cookie_file_from_env()
        try:
            is_url = bool(re.match(r"^https?://", query_text, re.I))


            if self._is_tiktok_url(query_text):
                return self._extract_generic_url(query_text, cookie_file, "TikTok")

            if self._is_youtube_url(query_text):
                return self._extract_youtube_url(query_text, cookie_file)

            if is_url:
                return self._extract_generic_url(query_text, cookie_file, "link")

            return self._extract_search(query_text, cookie_file)
        finally:
            if cookie_file and not os.getenv("YOUTUBE_COOKIES_FILE", "").strip():
                try:
                    os.unlink(cookie_file)
                except OSError:
                    pass

    @staticmethod
    def _is_tiktok_url(url):
        return bool(
            re.search(
                r"https?://(?:www\.)?(?:tiktok\.com|vm\.tiktok\.com)/",
                url,
                re.I,
            )
        )

    @staticmethod
    def _is_youtube_url(url):
        return bool(
            re.search(
                r"https?://(?:www\.)?(?:youtube\.com|music\.youtube\.com|youtu\.be)/",
                url,
                re.I,
            )
        )

    def _extract_search(self, query_text, cookie_file):
        errors = []

        for client in ("mweb", "web_safari", "android_vr"):
            try:
                opts = _youtube_opts(cookie_file, client)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(
                        f"ytsearch1:{query_text}",
                        download=False,
                    )

                track = self._info_to_track(info, query_text)
                if track:
                    return [track]

            except Exception as exc:
                errors.append(str(exc))
                LOG.warning("YouTube search failed (%s): %s", client, exc)

        raise RuntimeError(
            self._friendly_youtube_error(errors[-1] if errors else "")
        )

    def _extract_youtube_url(self, url, cookie_file):
        errors = []

        for client in ("mweb", "web_safari", "android_vr"):
            try:
                opts = _youtube_opts(cookie_file, client)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                track = self._info_to_track(info, url)
                if track:
                    return [track]

            except Exception as exc:
                errors.append(str(exc))
                LOG.warning(
                    "YouTube URL extraction failed (%s): %s",
                    client,
                    exc,
                )

        raise RuntimeError(
            self._friendly_youtube_error(errors[-1] if errors else "")
        )

    def _extract_generic_url(self, url, cookie_file, source_name):
        try:
            opts = _generic_opts(cookie_file)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            track = self._info_to_track(info, url)
            if track:
                return [track]

        except Exception as exc:
            LOG.warning("%s URL extraction failed: %s", source_name, exc)
            raise RuntimeError(
                self._friendly_source_error(source_name, str(exc))
            )

        raise RuntimeError(
            f"⚠️ {source_name} لینکەکە هیچ audio stream ـێکی بەردەستی نەدا."
        )

    @staticmethod
    def _info_to_track(info, fallback):
        if not info:
            return None

        if "entries" in info:
            info = next(
                (entry for entry in info.get("entries", []) if entry),
                None,
            )

        if not info:
            return None

        url = info.get("url") or info.get("webpage_url")
        if not url:
            return None

        return Track(
            info.get("title", fallback),
            url,
            info.get("webpage_url", fallback),
        )

    @staticmethod
    def _friendly_source_error(source_name, text):
        lower = (text or "").lower()

        if "unsupported url" in lower:
            return f"⚠️ ئەم {source_name} لینکە پشتگیری ناکرێت."

        if "private" in lower or "login" in lower:
            return f"⚠️ ئەم {source_name} لینکە تایبەتە یان login ـی دەوێت."

        if "no video" in lower or "no formats" in lower:
            return f"⚠️ {source_name} هیچ audio stream ـێکی بەردەست نەدا."

        return f"⚠️ نەتوانرا {source_name} لینکەکە بخوێندرێتەوە."

    @staticmethod
    def _friendly_youtube_error(text):
        lower = (text or "").lower()

        if "429" in lower or "too many requests" in lower:
            return (
                "⚠️ YouTube بۆ ئەم IP ـە rate-limit ـی کردووە. "
                "کەمێک چاوەڕێ بکە و دوبارە تاقی بکەرەوە."
            )

        if "sign in to confirm" in lower or "not a bot" in lower:
            return (
                "⚠️ YouTube bot-check ـی کردووە. "
                "bgutil POT provider لە Railway ـدا چالاکە؛ "
                "لە Deploy Logs ـدا دڵنیابە کە bgutil لە پۆرتی 4416 هەڵساوە."
            )

        if "javascript runtime" in lower:
            return (
                "⚠️ JavaScript runtime ـی YouTube بەردەست نییە؛ "
                "Railway redeploy بکە."
            )

        if "no formats" in lower or "no video" in lower:
            return "⚠️ هیچ audio stream ـێکی بەردەست نەبوو."

        return "⚠️ YouTube سەرچاوەی دەنگی نەدا؛ لینکێکی تری تاقی بکەرەوە."

    async def ensure_voice(self, interaction):
        if not interaction.guild:
            return None

        target = (
            interaction.user.voice.channel
            if interaction.user.voice
            else None
        )

        if not target:
            return None

        vc = interaction.guild.voice_client

        if vc and vc.is_connected():
            if vc.channel != target:
                await vc.move_to(target)
        else:
            vc = await target.connect()

        self.voice[interaction.guild.id] = vc
        return vc

    async def play_next(self, guild_id):
        vc = self.voice.get(guild_id)
        queue = self.queues.setdefault(guild_id, deque())
        current = self.current.get(guild_id)

        if not vc or not vc.is_connected():
            return

        if guild_id in self.skip_once:
            self.skip_once.discard(guild_id)
            current = None
            self.current.pop(guild_id, None)

        if self.loop.get(guild_id) and current:
            track = current
        elif queue:
            track = queue.popleft()
            self.current[guild_id] = track
        else:
            self.current.pop(guild_id, None)
            return

        def after(error):
            if error:
                LOG.error("FFmpeg playback error: %s", error)

            future = asyncio.run_coroutine_threadsafe(
                self.play_next(guild_id),
                self.bot.loop,
            )

            try:
                future.result(timeout=0)
            except Exception:
                pass

        source = discord.FFmpegPCMAudio(track.url, **FFMPEG_OPTS)
        source = discord.PCMVolumeTransformer(
            source,
            volume=self.volume.get(guild_id, 1.0),
        )

        vc.play(source, after=after)


def setup_music_commands(bot):
    if getattr(bot, "_hmb_music_commands_registered", False):
        return

    bot._hmb_music_commands_registered = True

    @bot.tree.command(
        name="play",
        description="لێدانی گۆرانی بە ناونیشان یان لینک",
    )
    @app_commands.describe(
        song="ناوی گۆرانی یان لینکی YouTube / TikTok"
    )
    async def play(interaction: discord.Interaction, song: str):
        try:
            vc = await bot.music.ensure_voice(interaction)

            if not vc:
                return await interaction.response.send_message(
                    "❌ تکایە سەرەتا بچۆ ناو کەناڵێکی دەنگییەوە.",
                    ephemeral=True,
                )

            await interaction.response.defer()

            tracks = await bot.music.extract(song)
            queue = bot.music.queues.setdefault(
                interaction.guild.id,
                deque(),
            )
            queue.extend(tracks)

            if not vc.is_playing() and not vc.is_paused():
                await bot.music.play_next(interaction.guild.id)

            if len(tracks) == 1:
                message = f"🎵 دانرا بۆ پەخشکردن: **{tracks[0].title}**"
            else:
                message = (
                    f"🎵 **{len(tracks)}** گۆرانی لە queue دانرا.\n"
                    f"▶️ یەکەم: **{tracks[0].title}**"
                )

            await interaction.followup.send(message)

        except Exception as e:
            LOG.exception("Play command failed")
            message = str(e).replace("`", "'")[:900]

            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ نەتوانرا گۆرانی پەخش بکرێت.\n{message}",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"❌ نەتوانرا گۆرانی پەخش بکرێت.\n{message}",
                    ephemeral=True,
                )

    @bot.tree.command(name="join", description="چوونە ناو voice channel")
    async def join(interaction: discord.Interaction):
        try:
            vc = await bot.music.ensure_voice(interaction)
        except Exception as e:
            return await interaction.response.send_message(
                f"❌ پەیوەندی بە voice نەکرا: `{str(e)[:500]}`",
                ephemeral=True,
            )

        await interaction.response.send_message(
            "✅ پەیوەندی بە voice کرا."
            if vc
            else "❌ لە voice channel نییت.",
            ephemeral=True,
        )

    @bot.tree.command(
        name="leave",
        description="دەرچوون لە voice channel",
    )
    async def leave(interaction: discord.Interaction):
        gid = interaction.guild.id
        vc = interaction.guild.voice_client if interaction.guild else None

        bot.music.loop[gid] = False
        bot.music.queues[gid] = deque()
        bot.music.current.pop(gid, None)
        bot.music.skip_once.discard(gid)

        if vc:
            await vc.disconnect(force=True)

        bot.music.voice.pop(gid, None)

        await interaction.response.send_message("👋 دەرچووم لە voice.")

    @bot.tree.command(name="pause", description="وەستاندنی گۆرانی")
    async def pause(interaction: discord.Interaction):
        vc = interaction.guild.voice_client if interaction.guild else None

        if vc and vc.is_playing():
            vc.pause()
            return await interaction.response.send_message("⏸️ وەستێنرا.")

        await interaction.response.send_message(
            "❌ هیچ گۆرانییەک لە پەخشکردندا نییە.",
            ephemeral=True,
        )

    @bot.tree.command(
        name="resume",
        description="دەستپێکردنەوەی گۆرانی",
    )
    async def resume(interaction: discord.Interaction):
        vc = interaction.guild.voice_client if interaction.guild else None

        if vc and vc.is_paused():
            vc.resume()
            return await interaction.response.send_message(
                "▶️ بەردەوام بوو."
            )

        await interaction.response.send_message(
            "❌ گۆرانی وەستاندراو نییە.",
            ephemeral=True,
        )

    @bot.tree.command(name="skip", description="تێپەڕاندنی گۆرانی")
    async def skip(interaction: discord.Interaction):
        gid = interaction.guild.id
        vc = interaction.guild.voice_client if interaction.guild else None

        if vc and (vc.is_playing() or vc.is_paused()):
            bot.music.skip_once.add(gid)
            vc.stop()
            return await interaction.response.send_message(
                "⏭️ Skip کرا."
            )

        await interaction.response.send_message(
            "❌ هیچ گۆرانییەک نییە.",
            ephemeral=True,
        )

    @bot.tree.command(
        name="stop",
        description="وەستاندن و پاککردنەوەی queue",
    )
    async def stop(interaction: discord.Interaction):
        gid = interaction.guild.id
        vc = interaction.guild.voice_client if interaction.guild else None

        bot.music.loop[gid] = False
        bot.music.skip_once.discard(gid)
        bot.music.current.pop(gid, None)
        bot.music.queues[gid] = deque()

        if vc:
            vc.stop()

        await interaction.response.send_message(
            "⏹️ پەخشکردن و queue وەستاندرا."
        )

    @bot.tree.command(name="queue", description="بینینی queue")
    async def queue(interaction: discord.Interaction):
        gid = interaction.guild.id
        q = bot.music.queues.get(gid, deque())
        cur = bot.music.current.get(gid)

        text = f"🎵 ئێستا: **{cur.title}**\n" if cur else ""
        text += "\n".join(
            f"{i + 1}. {x.title}" for i, x in enumerate(q)
        ) or "Queue بەتاڵە."

        await interaction.response.send_message(text[:4000])

    @bot.tree.command(name="shuffle", description="تێکەڵکردنی queue")
    async def shuffle(interaction: discord.Interaction):
        gid = interaction.guild.id
        q = bot.music.queues.get(gid, deque())

        if len(q) < 2:
            return await interaction.response.send_message(
                "❌ بۆ shuffle ـکردن کەمتر لە ٢ گۆرانی لە queue ـە.",
                ephemeral=True,
            )

        items = list(q)
        random.shuffle(items)
        bot.music.queues[gid] = deque(items)

        await interaction.response.send_message("🔀 Queue تێکەڵکرا.")

    @bot.tree.command(
        name="nowplaying",
        description="پیشاندانی گۆرانیی ئێستا",
    )
    async def nowplaying(interaction: discord.Interaction):
        gid = interaction.guild.id
        cur = bot.music.current.get(gid)

        if not cur:
            return await interaction.response.send_message(
                "❌ هیچ گۆرانییەک لە پەخشکردندا نییە.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"🎶 ئێستا: **{cur.title}**\n🔗 {cur.webpage}"
        )

    @bot.tree.command(
        name="clearqueue",
        description="پاککردنەوەی queue بەبێ وەستاندنی گۆرانیی ئێستا",
    )
    async def clearqueue(interaction: discord.Interaction):
        bot.music.queues[interaction.guild.id] = deque()
        await interaction.response.send_message("🧹 Queue پاککرایەوە.")

    @bot.tree.command(
        name="remove",
        description="لابردنی دانەیەک لە queue",
    )
    @app_commands.describe(position="ژمارەی گۆرانی لە queue")
    async def remove(
        interaction: discord.Interaction,
        position: int,
    ):
        gid = interaction.guild.id
        q = bot.music.queues.get(gid, deque())

        if position < 1 or position > len(q):
            return await interaction.response.send_message(
                "❌ ژمارەی queue هەڵەیە.",
                ephemeral=True,
            )

        items = list(q)
        removed = items.pop(position - 1)
        bot.music.queues[gid] = deque(items)

        await interaction.response.send_message(
            f"🗑️ **{removed.title}** لە queue لابرا."
        )

    @bot.tree.command(name="volume", description="گۆڕینی دەنگ")
    @app_commands.describe(value="0-100")
    async def volume(
        interaction: discord.Interaction,
        value: int,
    ):
        if not 0 <= value <= 100:
            return await interaction.response.send_message(
                "❌ ژمارەکە دەبێت 0 تا 100 بێت.",
                ephemeral=True,
            )

        gid = interaction.guild.id
        bot.music.volume[gid] = value / 100
        vc = interaction.guild.voice_client

        if (
            vc
            and vc.source
            and isinstance(vc.source, discord.PCMVolumeTransformer)
        ):
            vc.source.volume = value / 100

        await interaction.response.send_message(
            f"🔊 Volume بۆ **{value}%** دانرا."
        )

    @bot.tree.command(
        name="loop",
        description="دووبارەکردنەوەی گۆرانی",
    )
    async def loop(interaction: discord.Interaction):
        gid = interaction.guild.id
        bot.music.loop[gid] = not bot.music.loop.get(gid, False)

        await interaction.response.send_message(
            f"🔁 Loop: {'ON' if bot.music.loop[gid] else 'OFF'}"
        )
