import asyncio
import logging
import os
import re
import random
import subprocess
import sys
from collections import deque

import discord
from discord import app_commands
import yt_dlp


YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch1",
    "extract_flat": False,
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


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
        """Resolve a music query from YouTube, TikTok, Spotify, or any
        URL supported by yt-dlp. Spotify is resolved to YouTube sources
        through spotDL, so Spotify tracks/playlists do not get passed to
        yt-dlp directly.
        """
        loop = asyncio.get_running_loop()

        query_text = str(query or "").strip()
        if not query_text:
            raise RuntimeError("تکایە ناوی گۆرانی یان لینکێک بنووسە.")

        def work():
            current_query = query_text
            is_url = bool(re.match(r"^https?://", current_query, re.I))
            is_spotify = bool(
                re.search(r"https?://(?:open\.)?spotify\.com/", current_query, re.I)
                or re.search(r"https?://spotify\.link/", current_query, re.I)
            )

            # Spotify itself does not provide a raw audio URL for this bot.
            # spotDL resolves Spotify tracks/playlists to matching YouTube
            # sources, which are then streamed by yt-dlp.
            if is_spotify:
                try:
                    proc = subprocess.run(
                        [sys.executable, "-m", "spotdl", "url", current_query],
                        capture_output=True,
                        text=True,
                        timeout=90,
                        check=False,
                    )
                except FileNotFoundError:
                    raise RuntimeError(
                        "Spotify support بۆ spotDL دامەزرابوو نییە."
                    )

                urls = re.findall(
                    r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s]+|youtu\.be/[^\s]+)",
                    proc.stdout or "",
                )
                if not urls:
                    details = (proc.stderr or proc.stdout or "").strip()
                    raise RuntimeError(
                        "نەتوانرا Spotify لینکەکە بۆ گۆرانییەکی YouTube بگۆڕدرێت."
                        + (f" {details[-250:]}" if details else "")
                    )

                # Return all resolved Spotify items; play() will queue them.
                tracks = []
                with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                    for source_url in urls[:100]:
                        try:
                            info = ydl.extract_info(source_url, download=False)
                            if not info:
                                continue
                            if "entries" in info:
                                info = next(
                                    (entry for entry in info["entries"] if entry),
                                    None,
                                )
                            if not info:
                                continue
                            audio_url = info.get("url") or info.get("webpage_url")
                            if audio_url:
                                tracks.append(
                                    Track(
                                        info.get("title", source_url),
                                        audio_url,
                                        info.get("webpage_url", source_url),
                                    )
                                )
                        except Exception as exc:
                            logging.getLogger("HMB_GLOBAL").warning(
                                "Spotify item skipped: %s", exc
                            )
                if not tracks:
                    raise RuntimeError(
                        "Spotify لینکەکە دۆزرایەوە، بەڵام هیچ سەرچاوەیەکی دەنگی بەردەست نەبوو."
                    )
                return tracks

            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                try:
                    info = ydl.extract_info(current_query, download=False)
                except Exception as first_error:
                    # If a direct video is blocked/DRM-protected, try a
                    # YouTube search using the URL text as a last-resort
                    # fallback instead of crashing the command.
                    if is_url:
                        try:
                            fallback = ydl.extract_info(
                                f"ytsearch1:{current_query}",
                                download=False,
                            )
                            info = (
                                next(
                                    (entry for entry in fallback.get("entries", []) if entry),
                                    None,
                                )
                                if fallback
                                else None
                            )
                        except Exception:
                            raise first_error
                    else:
                        raise

                if not info:
                    raise RuntimeError("هیچ ئەنجامێک نەدۆزرایەوە.")
                if "entries" in info:
                    info = next((entry for entry in info["entries"] if entry), None)
                if not info:
                    raise RuntimeError("هیچ گۆرانییەک نەدۆزرایەوە.")

                url = info.get("url") or info.get("webpage_url")
                if not url:
                    raise RuntimeError("لینکی دەنگی گۆرانی نەدۆزرایەوە.")

                return [
                    Track(
                        info.get("title", current_query),
                        url,
                        info.get("webpage_url"),
                    )
                ]

        return await loop.run_in_executor(None, work)

    async def ensure_voice(self, interaction):
        if not interaction.guild:
            return None

        target = interaction.user.voice.channel if interaction.user.voice else None
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

        skip_this_track = guild_id in self.skip_once
        if skip_this_track:
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
                logging.getLogger("HMB_GLOBAL").error(
                    "FFmpeg playback error: %s", error
                )
            future = asyncio.run_coroutine_threadsafe(
                self.play_next(guild_id), self.bot.loop
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
    # setup_hook should be safe if invoked more than once.
    if getattr(bot, "_hmb_music_commands_registered", False):
        return
    bot._hmb_music_commands_registered = True

    @bot.tree.command(
        name="play",
        description="لێدانی گۆرانی بە ناونیشان یان لینک",
    )
    @app_commands.describe(song="ناوی گۆرانی یان لینکی یوتیوب")
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
            if not isinstance(tracks, list):
                tracks = [tracks]

            queue = bot.music.queues.setdefault(
                interaction.guild.id, deque()
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
            logging.getLogger("HMB_GLOBAL").exception("Play command failed")
            message = str(e).replace("`", "'")[:500]
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ نەتوانرا گۆرانی پەخش بکرێت.\n`{message}`",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"❌ نەتوانرا گۆرانی پەخش بکرێت.\n`{message}`",
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

    @bot.tree.command(name="leave", description="دەرچوون لە voice channel")
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

    @bot.tree.command(name="resume", description="دەستپێکردنەوەی گۆرانی")
    async def resume(interaction: discord.Interaction):
        vc = interaction.guild.voice_client if interaction.guild else None
        if vc and vc.is_paused():
            vc.resume()
            return await interaction.response.send_message("▶️ بەردەوام بوو.")
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
            return await interaction.response.send_message("⏭️ Skip کرا.")
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
        text += (
            "\n".join(f"{i + 1}. {x.title}" for i, x in enumerate(q))
            or "Queue بەتاڵە."
        )
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

    @bot.tree.command(name="nowplaying", description="پیشاندانی گۆرانیی ئێستا")
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

    @bot.tree.command(name="clearqueue", description="پاککردنەوەی queue بەبێ وەستاندنی گۆرانیی ئێستا")
    async def clearqueue(interaction: discord.Interaction):
        gid = interaction.guild.id
        bot.music.queues[gid] = deque()
        await interaction.response.send_message("🧹 Queue پاککرایەوە.")

    @bot.tree.command(name="remove", description="لابردنی دانەیەک لە queue")
    @app_commands.describe(position="ژمارەی گۆرانی لە queue")
    async def remove(interaction: discord.Interaction, position: int):
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
    async def volume(interaction: discord.Interaction, value: int):
        if not 0 <= value <= 100:
            return await interaction.response.send_message(
                "❌ ژمارەکە دەبێت 0 تا 100 بێت.",
                ephemeral=True,
            )

        gid = interaction.guild.id
        bot.music.volume[gid] = value / 100

        vc = interaction.guild.voice_client
        if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = value / 100

        await interaction.response.send_message(
            f"🔊 Volume بۆ **{value}%** دانرا."
        )

    @bot.tree.command(name="loop", description="دووبارەکردنەوەی گۆرانی")
    async def loop(interaction: discord.Interaction):
        gid = interaction.guild.id
        bot.music.loop[gid] = not bot.music.loop.get(gid, False)
        await interaction.response.send_message(
            f"🔁 Loop: {'ON' if bot.music.loop[gid] else 'OFF'}"
        )
