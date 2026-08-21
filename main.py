import os
import time
import asyncio
import logging
import random
import re
import inspect
import shlex
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
from features import setup_features
from music import MusicManager, setup_music_commands
from extras import setup_extra_commands
from storage import Store


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BASE = Path(__file__).parent

TOKEN = os.getenv("TOKEN", "").strip()

PREFIX = os.getenv("PREFIX", "$").strip() or "$"

PORT = int(os.getenv("PORT", "3000"))

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

REGISTER_COMMANDS = (
    os.getenv("REGISTER_COMMANDS", "false").lower() == "true"
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
# PREFIX RESPONSE
# =========================================================

class _PrefixResponse:

    def __init__(self, interaction):
        self.interaction = interaction
        self._done = False
        self._message = None

    def is_done(self):
        return self._done

    async def send_message(
        self,
        content=None,
        *,
        ephemeral=False,
        **kwargs
    ):
        self._done = True

        allowed = {
            k: v
            for k, v in kwargs.items()
            if k in (
                "embed",
                "embeds",
                "file",
                "files",
                "view",
                "allowed_mentions"
            )
        }

        self._message = await self.interaction.channel.send(
            content or "",
            **allowed
        )

        return self._message

    async def defer(
        self,
        *,
        ephemeral=False,
        **kwargs
    ):
        self._done = True


# =========================================================
# PREFIX FOLLOWUP
# =========================================================

class _PrefixFollowup:

    def __init__(self, interaction):
        self.interaction = interaction

    async def send(
        self,
        content=None,
        *,
        ephemeral=False,
        **kwargs
    ):
        allowed = {
            k: v
            for k, v in kwargs.items()
            if k in (
                "embed",
                "embeds",
                "file",
                "files",
                "view",
                "allowed_mentions"
            )
        }

        return await self.interaction.channel.send(
            content or "",
            **allowed
        )


# =========================================================
# PREFIX INTERACTION
# =========================================================

class _PrefixInteraction:

    """
    Interaction-compatible adapter.

    This allows the existing slash commands
    to also work with the $ prefix.
    """

    def __init__(self, message, bot):

        self.message = message

        self.client = bot

        self.guild = message.guild

        self.channel = message.channel

        self.user = message.author

        self.guild_id = (
            message.guild.id
            if message.guild
            else None
        )

        self.channel_id = (
            message.channel.id
            if message.channel
            else None
        )

        self.response = _PrefixResponse(self)

        self.followup = _PrefixFollowup(self)

        self.command = None

    @property
    def permissions(self):

        if self.guild:

            return self.user.guild_permissions

        return discord.Permissions.none()

    async def original_response(self):

        return self.response._message


# =========================================================
# ARGUMENT CONVERTER
# =========================================================

async def _prefix_convert(
    ctx,
    raw,
    annotation
):

    if annotation is int:

        return int(raw)

    if annotation is discord.Member:

        return await commands.MemberConverter().convert(
            ctx,
            raw
        )

    if annotation is discord.User:

        return await commands.UserConverter().convert(
            ctx,
            raw
        )

    if annotation is discord.Role:

        return await commands.RoleConverter().convert(
            ctx,
            raw
        )

    if annotation is discord.TextChannel:

        return await commands.TextChannelConverter().convert(
            ctx,
            raw
        )

    return raw


# =========================================================
# PREFIX ARGUMENT PARSER
# =========================================================

async def _prefix_arguments(
    ctx,
    callback,
    raw
):

    sig = inspect.signature(callback)

    params = list(
        sig.parameters.values()
    )[1:]

    tokens = (
        shlex.split(raw)
        if raw
        else []
    )

    values = {}

    pos = 0

    for i, p in enumerate(params):

        ann = p.annotation

        has_default = (
            p.default
            is not inspect.Parameter.empty
        )

        remaining = len(tokens) - pos

        if remaining <= 0:

            if has_default:

                values[p.name] = p.default

                continue

            raise ValueError(
                f"❌ بۆ `${ctx.invoked_with}` "
                f"پێویستە `{p.name}` بنووسیت."
            )

        # -------------------------------------------------
        # STRING ARGUMENT
        # -------------------------------------------------

        if ann is str:

            later_required = sum(
                1
                for q in params[i + 1:]
                if q.default
                is inspect.Parameter.empty
            )

            take = max(
                1,
                remaining - later_required
            )

            if later_required == 0:

                take = remaining

            raw_value = " ".join(
                tokens[pos:pos + take]
            )

            pos += take

        # -------------------------------------------------
        # OTHER ARGUMENTS
        # -------------------------------------------------

        else:

            raw_value = tokens[pos]

            pos += 1

        try:

            values[p.name] = await _prefix_convert(
                ctx,
                raw_value,
                ann
            )

        except Exception:

            pretty = getattr(
                ann,
                "__name__",
                str(ann)
            )

            raise ValueError(
                f"❌ ناتوانم `{raw_value}` "
                f"وەک {pretty} بناسم."
            )

    if pos < len(tokens):

        raise ValueError(
            f"❌ ژمارەی arguments زۆرە "
            f"بۆ `${ctx.invoked_with}`."
        )

    return values


# =========================================================
# REGISTER $ PREFIX COMMANDS
# =========================================================

def _register_prefix_commands(bot):

    """
    Every existing slash command is also registered
    as a $ prefix command.
    """

    for app_cmd in bot.tree.get_commands():

        if not isinstance(
            app_cmd,
            app_commands.Command
        ):
            continue

        name = app_cmd.name

        if bot.get_command(name):

            continue

        def make_runner(
            _app_cmd,
            _name
        ):

            async def runner(ctx):

                interaction = _PrefixInteraction(
                    ctx.message,
                    bot
                )

                interaction.command = _app_cmd

                try:

                    # -------------------------------------
                    # PERMISSION CHECKS
                    # -------------------------------------

                    for check in getattr(
                        _app_cmd,
                        "checks",
                        []
                    ):

                        result = check(
                            interaction
                        )

                        if inspect.isawaitable(
                            result
                        ):

                            result = await result

                        if not result:

                            raise app_commands.CheckFailure(
                                "prefix permission check failed"
                            )

                    # -------------------------------------
                    # COMMAND TEXT
                    # -------------------------------------

                    raw = ctx.message.content[
                        len(PREFIX) + len(_name):
                    ].strip()

                    # -------------------------------------
                    # ARGUMENTS
                    # -------------------------------------

                    kwargs = await _prefix_arguments(
                        ctx,
                        _app_cmd.callback,
                        raw
                    )

                    # -------------------------------------
                    # RUN COMMAND
                    # -------------------------------------

                    await _app_cmd.callback(
                        interaction,
                        **kwargs
                    )

                except app_commands.MissingPermissions:

                    await ctx.send(
                        "❌ ڕێگەت پێنەدراوە."
                    )

                except app_commands.CheckFailure:

                    await ctx.send(
                        "❌ ڕێگەت پێنەدراوە."
                    )

                except ValueError as e:

                    await ctx.send(
                        str(e)
                    )

                except Exception:

                    log.exception(
                        "Prefix command %s failed",
                        _name
                    )

                    await ctx.send(
                        "❌ هەڵەیەکی نەخوازراو ڕوویدا."
                    )

            runner.__name__ = (
                f"prefix_{_name}"
            )

            runner.__doc__ = (
                f"{PREFIX}{_name} command"
            )

            return runner

        bot.add_command(
            commands.Command(
                make_runner(
                    app_cmd,
                    name
                ),
                name=name
            )
        )



# =========================================================
# SAFE COMMAND SYNC
# =========================================================

def _sync_command_handlers(bot):
    """Add low-risk prefix controls for slash-command registration."""
    if bot.get_command("sync"):
        return

    @bot.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_current_guild(ctx):
        """Sync slash commands to this server without a global rate-limit burst."""
        if not ctx.guild:
            return await ctx.send("❌ ئەم فرمانە تەنها لە سێروەر کاردەکات.")

        try:
            synced = await bot.tree.sync(guild=ctx.guild)
            await ctx.send(
                f"✅ **{len(synced)}** Slash Command بۆ **{ctx.guild.name}** تۆمارکرا.\n"
                "ئێستا دەتوانیت `/` بنووسیت و command ـەکان ببینیت."
            )
        except discord.HTTPException as exc:
            retry = getattr(exc, "retry_after", None)
            extra = f" ⏳ دووبارە هەوڵ بدەرەوە دوای {retry:.1f}s." if retry else ""
            await ctx.send(f"❌ Sync سەرکەوتوو نەبوو.{extra}")

    @bot.command(name="syncglobal")
    async def sync_global(ctx):
        """Owner-only explicit global sync."""
        if OWNER_ID and ctx.author.id != OWNER_ID:
            return await ctx.send("❌ تەنها خاوەن بۆتەکە دەتوانێت global sync بکات.")
        if not OWNER_ID or ctx.author.id != OWNER_ID:
            return await ctx.send("❌ OWNER_ID لە Railway Variables دانەنراوە.")

        try:
            synced = await bot.tree.sync()
            await ctx.send(
                f"✅ **{len(synced)}** Slash Command بە شێوەی global sync کرا.\n"
                "لە Discord ـدا بڵاوبوونەوەی global command لەوانەیە کەمێک کات بخایەنێت."
            )
        except discord.HTTPException as exc:
            retry = getattr(exc, "retry_after", None)
            extra = f" ⏳ دووبارە هەوڵ بدەرەوە دوای {retry:.1f}s." if retry else ""
            await ctx.send(f"❌ Global sync سەرکەوتوو نەبوو.{extra}")


# =========================================================
# HMB GLOBAL BOT
# =========================================================

class HMBGlobal(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix=PREFIX,
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

        # Register $ commands
        _register_prefix_commands(self)
        _sync_command_handlers(self)

        # Global slash-command sync is OFF by default to avoid Discord 429
        # rate limits during Railway restarts. Use $sync in a server to
        # register commands to that server immediately, or explicitly set
        # REGISTER_COMMANDS=true when you intentionally want a global sync.
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
                    name="/help • $help | HMB GLOBAL"
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
