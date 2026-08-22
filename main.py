import os
import time
import asyncio
import logging
import random
import re
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path
from threading import Thread

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask, jsonify

from moderation import setup_moderation
from features import setup_features, register_persistent_help_views
from music import MusicManager, setup_music_commands
from extras import setup_extra_commands
from storage import Store


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BASE = Path(__file__).parent

TOKEN = os.getenv("TOKEN", "").strip()


PORT = int(os.getenv("PORT", "3000"))

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

REGISTER_COMMANDS = (
    os.getenv("REGISTER_COMMANDS", "true").lower() == "true"
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("hmb")


# =========================================================
# DISCORD INTENTS
# =========================================================

intents = discord.Intents.default()

# Required for reading normal Discord messages
intents.message_content = True

# Required for member events / member based features
intents.members = True
# Required for voice channel connections / music playback
intents.voice_states = True


# =========================================================
# HMB GLOBAL BOT
# =========================================================

class HMBGlobal(commands.Bot):

    def __init__(self):

        # Prefix commands are disabled; this bot uses slash commands only.
        super().__init__(
            command_prefix="__HMB_DISABLED_PREFIX__",
            intents=intents,
            help_command=None
        )

        self.music = MusicManager(self)

        self.spam = defaultdict(deque)
        self.spam_last_text = {}
        self.spam_repeats = defaultdict(int)
        self.spam_triggered_until = {}

        self.started = time.time()

        self.store = Store(
            BASE / "hmb.sqlite3"
        )

    # =====================================================
    # SETUP
    # =====================================================

    async def setup_hook(self):

        setup_moderation(self)

        setup_features(self)

        setup_music_commands(self)

        setup_extra_commands(self)

        # Restore Help button handlers after Railway restarts.
        register_persistent_help_views(self)

        # Register slash commands. Enabled by default so commands are
        # registered after a Railway redeploy.
        if REGISTER_COMMANDS:
            try:
                synced = await self.tree.sync()
                log.info("Registered %d global slash commands", len(synced))
            except Exception:
                log.exception("Global slash command registration failed")

    # =====================================================
    # READY
    # =====================================================

    async def on_ready(self):

        log.info(
            "HMB GLOBAL IS ONLINE | %s (%s) | servers=%d",
            self.user,
            self.user.id,
            len(self.guilds)
        )

        try:

            await self.change_presence(

                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="/help | HMB GLOBAL"
                ),

                status=discord.Status.online
            )

        except Exception:

            pass

    # =====================================================
    # PREFIX ERROR
    # =====================================================

    async def on_command_error(
        self,
        ctx,
        error
    ):

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            try:
                await ctx.send("❌ ڕێگەت پێنەدراوە.")
            except Exception:
                pass
            return

        log.exception(
            "Prefix command error",
            exc_info=error
        )

        try:

            await ctx.send(
                "❌ هەڵەیەکی نەخوازراو ڕوویدا."
            )

        except Exception:

            pass


# =========================================================
# BOT INSTANCE
# =========================================================

bot = HMBGlobal()


# =========================================================
# MEMBER JOIN
# =========================================================

@bot.event
async def on_member_join(
    member: discord.Member
):

    # -----------------------------------------------------
    # AUTOROLE
    # -----------------------------------------------------

    role_id = bot.store.get_int(
        member.guild.id,
        "autorole"
    )

    if role_id:

        role = member.guild.get_role(
            role_id
        )

        if role:

            try:

                await member.add_roles(
                    role,
                    reason="HMB GLOBAL autorole"
                )

            except discord.HTTPException:

                pass

    # -----------------------------------------------------
    # WELCOME
    # -----------------------------------------------------

    channel_id = bot.store.get_int(
        member.guild.id,
        "welcome_channel"
    )

    if channel_id:

        channel = member.guild.get_channel(
            channel_id
        )

        if channel:

            try:

                await channel.send(
                    f"👋 بەخێربێیت "
                    f"{member.mention} "
                    f"بۆ **{member.guild.name}**!"
                )

            except discord.HTTPException:

                pass


# =========================================================
# MESSAGE EVENT
# =========================================================

@bot.event
async def on_message(
    message: discord.Message
):

    # Ignore bots
    if message.author.bot:

        return

    # Ignore DMs
    if not message.guild:

        return

    # =====================================================
    # LINK PROTECTION
    # =====================================================

    if bot.store.get_bool(
        message.guild.id,
        "link_protection"
    ):

        if (
            not message.author.guild_permissions.administrator
            and re.search(
                r"(?:https?://|www\.)\S+",
                message.content,
                re.I
            )
        ):

            try:

                await message.delete()

                notice = await message.channel.send(
                    f"🔗 <@{message.author.id}> "
                    f"لینک لەم کەناڵەدا ڕێگەپێنەدراوە."
                )

                await asyncio.sleep(5)

                await notice.delete()

            except discord.HTTPException:

                pass

            return

    # =====================================================
    # STRONG ANTISPAM
    # =====================================================

    if bot.store.get_bool(message.guild.id, "antispam"):
        if not (
            message.author.guild_permissions.administrator
            or message.author.guild_permissions.manage_messages
        ):
            key = (message.guild.id, message.author.id)
            now = time.monotonic()
            q = bot.spam[key]
            q.append(now)
            while q and now - q[0] > 7:
                q.popleft()

            normalized = " ".join(message.content.lower().split())[:400]
            if normalized and normalized == bot.spam_last_text.get(key):
                bot.spam_repeats[key] += 1
            else:
                bot.spam_repeats[key] = 1
                bot.spam_last_text[key] = normalized

            mention_flood = len(message.mentions) + len(message.role_mentions) >= 5
            fast_burst = len(q) >= 5
            duplicate_flood = bot.spam_repeats[key] >= 3
            long_flood = len(message.content) >= 1800
            triggered = fast_burst or duplicate_flood or mention_flood or long_flood

            if triggered and now >= bot.spam_triggered_until.get(key, 0):
                bot.spam_triggered_until[key] = now + 600

                # Delete the triggering message first.
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

                # Delete the offender's messages from this channel.
                # discord.py uses bulk deletion where Discord permits it and
                # falls back to individual deletion for older messages.
                try:
                    deleted = await message.channel.purge(
                        limit=None,
                        check=lambda m: m.author.id == message.author.id,
                        bulk=True,
                        reason="HMB GLOBAL anti-spam cleanup",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    deleted = []

                # 10-minute timeout.
                timeout_ok = False
                try:
                    await message.author.timeout(
                        discord.utils.utcnow() + timedelta(minutes=10),
                        reason="HMB GLOBAL anti-spam: 10 minute timeout",
                    )
                    timeout_ok = True
                except (discord.Forbidden, discord.HTTPException):
                    pass

                try:
                    await message.channel.send(
                        f"🛡️ **Anti-Spam چالاک بوو**\n"
                        f"👤 {message.author.mention}\n"
                        f"🗑️ **{len(deleted)}** پەیامی ئەم کەسە لەم کەناڵە سڕایەوە.\n"
                        f"🔇 Timeout: **10 خولەک** {'✅' if timeout_ok else '⚠️'}",
                        delete_after=8,
                    )
                except discord.HTTPException:
                    pass

                bot.spam[key].clear()
                bot.spam_repeats[key] = 0
                return

    # =====================================================
    # PREFIX COMMAND PROCESSOR
    # =====================================================

    await bot.process_commands(
        message
    )


# =========================================================
# FLASK HEALTH SERVER
# =========================================================

app = Flask(__name__)


@app.get("/")
def root():

    return (
        "HMB GLOBAL is active and running!",
        200
    )


@app.get("/health")
def health():

    return jsonify(
        status="online",
        bot="HMB GLOBAL",
        uptime=time.time() - bot.started
    ), 200


# =========================================================
# WEB SERVER
# =========================================================

def run_web():

    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False
    )


# =========================================================
# START BOT
# =========================================================

if __name__ == "__main__":

    if not TOKEN:

        raise SystemExit(
            "TOKEN is missing from Railway Variables!"
        )

    # Start Railway health server
    Thread(
        target=run_web,
        daemon=True
    ).start()

    # Start Discord bot
    bot.run(
        TOKEN,
        log_handler=None
    )
