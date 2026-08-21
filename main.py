import os
import time
import asyncio
import logging
import random
import re
import inspect
import shlex
from collections import defaultdict, deque
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

load_dotenv()
BASE = Path(__file__).parent
TOKEN = os.getenv("TOKEN", "").strip()
PREFIX = "$"  # HMB GLOBAL prefix: use $ for all prefix commands
PORT = int(os.getenv("PORT", "3000"))
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
REGISTER_COMMANDS = os.getenv("REGISTER_COMMANDS", "true").lower() == "true"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

class _PrefixResponse:
    def __init__(self, interaction):
        self.interaction = interaction
        self._done = False
        self._message = None

    def is_done(self):
        return self._done

    async def send_message(self, content=None, *, ephemeral=False, **kwargs):
        self._done = True
        self._message = await self.interaction.channel.send(content or "", **{
            k: v for k, v in kwargs.items()
            if k in ("embed", "embeds", "file", "files", "view", "allowed_mentions")
        })
        return self._message

    async def defer(self, *, ephemeral=False, **kwargs):
        self._done = True


class _PrefixFollowup:
    def __init__(self, interaction):
        self.interaction = interaction

    async def send(self, content=None, *, ephemeral=False, **kwargs):
        return await self.interaction.channel.send(content or "", **{
            k: v for k, v in kwargs.items()
            if k in ("embed", "embeds", "file", "files", "view", "allowed_mentions")
        })


class _PrefixInteraction:
    """Small Interaction-compatible adapter so the existing Python commands
    can be called from $prefix messages without duplicating every command."""
    def __init__(self, message, bot):
        self.message = message
        self.client = bot
        self.guild = message.guild
        self.channel = message.channel
        self.user = message.author
        self.guild_id = message.guild.id if message.guild else None
        self.channel_id = message.channel.id if message.channel else None
        self.response = _PrefixResponse(self)
        self.followup = _PrefixFollowup(self)
        self.command = None

    @property
    def permissions(self):
        return self.user.guild_permissions if self.guild else discord.Permissions.none()

    async def original_response(self):
        return self.response._message


async def _prefix_convert(ctx, raw, annotation):
    if annotation is int:
        return int(raw)
    if annotation is discord.Member:
        return await commands.MemberConverter().convert(ctx, raw)
    if annotation is discord.User:
        return await commands.UserConverter().convert(ctx, raw)
    if annotation is discord.Role:
        return await commands.RoleConverter().convert(ctx, raw)
    if annotation is discord.TextChannel:
        return await commands.TextChannelConverter().convert(ctx, raw)
    return raw


async def _prefix_arguments(ctx, callback, raw):
    sig = inspect.signature(callback)
    params = list(sig.parameters.values())[1:]  # skip interaction
    tokens = shlex.split(raw) if raw else []
    values = {}
    pos = 0

    for i, p in enumerate(params):
        ann = p.annotation
        has_default = p.default is not inspect.Parameter.empty
        remaining = len(tokens) - pos

        if remaining <= 0:
            if has_default:
                values[p.name] = p.default
                continue
            raise ValueError(f"❌ بۆ `${ctx.invoked_with}` پێویستە `{p.name}` بنووسیت.")

        # A string parameter consumes the rest, except when a later parameter
        # still needs a token (e.g. $giveaway prize 3).
        if ann is str:
            later_required = sum(
                1 for q in params[i+1:]
                if q.default is inspect.Parameter.empty
            )
            take = max(1, remaining - later_required)
            # If all later parameters are optional, keep all remaining text.
            if later_required == 0:
                take = remaining
            raw_value = " ".join(tokens[pos:pos+take])
            pos += take
        else:
            raw_value = tokens[pos]
            pos += 1

        try:
            values[p.name] = await _prefix_convert(ctx, raw_value, ann)
        except Exception:
            pretty = getattr(ann, "__name__", str(ann))
            raise ValueError(f"❌ ناتوانم `{raw_value}` وەک {pretty} بناسم.")

    if pos < len(tokens):
        raise ValueError(f"❌ ژمارەی arguments زۆرە بۆ `${ctx.invoked_with}`.")

    return values


def _register_prefix_commands(bot):
    """Expose every existing slash command with the configured $ prefix."""
    for app_cmd in bot.tree.get_commands():
        if not isinstance(app_cmd, app_commands.Command):
            continue
        name = app_cmd.name
        if bot.get_command(name):
            continue

        def make_runner(_app_cmd, _name):
            async def runner(ctx):
                interaction = _PrefixInteraction(ctx.message, bot)
                interaction.command = _app_cmd
                try:
                    # Reuse the same permission checks already attached to the
                    # slash command, so $ commands are not weaker than / commands.
                    for check in getattr(_app_cmd, "checks", []):
                        result = check(interaction)
                        if inspect.isawaitable(result):
                            result = await result
                        if not result:
                            raise app_commands.CheckFailure("prefix permission check failed")

                    raw = ctx.message.content[len(PREFIX) + len(_name):].strip()
                    kwargs = await _prefix_arguments(ctx, _app_cmd.callback, raw)
                    await _app_cmd.callback(interaction, **kwargs)
                except app_commands.MissingPermissions:
                    await ctx.send("❌ ڕێگەت پێنەدراوە.")
                except app_commands.CheckFailure:
                    await ctx.send("❌ ڕێگەت پێنەدراوە.")
                except ValueError as e:
                    await ctx.send(str(e))
                except Exception as e:
                    log.exception("Prefix command %s failed", _name, exc_info=e)
                    await ctx.send("❌ هەڵەیەکی نەخوازراو ڕوویدا.")

            runner.__name__ = f"prefix_{_name}"
            runner.__doc__ = f"{PREFIX}{_name} command"
            return runner

        bot.add_command(commands.Command(make_runner(app_cmd, name), name=name))


class HMBGlobal(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.music = MusicManager(self)
        self.spam = defaultdict(deque)
        self.started = time.time()
        self.store = Store(BASE / "hmb.sqlite3")

    async def setup_hook(self):
        setup_moderation(self)
        setup_features(self)
        setup_music_commands(self)
        setup_extra_commands(self)
        _register_prefix_commands(self)
        if REGISTER_COMMANDS:
            try:
                synced = await self.tree.sync()
                log.info("Registered %d Python slash commands", len(synced))
            except Exception:
                log.exception("Slash command registration failed")

    async def on_ready(self):
        log.info("HMB GLOBAL IS ONLINE | %s (%s) | servers=%d", self.user, self.user.id, len(self.guilds))
        try:
            await self.change_presence(
                activity=discord.Activity(type=discord.ActivityType.listening, name="HMB GLOBAL • Python"),
                status=discord.Status.online,
            )
        except Exception:
            pass

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        log.exception("Prefix command error", exc_info=error)
        try:
            await ctx.send("❌ هەڵەیەکی نەخوازراو ڕوویدا.")
        except Exception:
            pass

bot = HMBGlobal()

@bot.event
async def on_member_join(member: discord.Member):
    role_id = bot.store.get_int(member.guild.id, "autorole")
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="HMB GLOBAL autorole")
            except discord.HTTPException:
                pass
    channel_id = bot.store.get_int(member.guild.id, "welcome_channel")
    if channel_id:
        channel = member.guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(f"👋 بەخێربێیت {member.mention} بۆ **{member.guild.name}**!")
            except discord.HTTPException:
                pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # Link protection
    if bot.store.get_bool(message.guild.id, "link_protection"):
        if not message.author.guild_permissions.administrator and re.search(r"(?:https?://|www\.)\S+", message.content, re.I):
            try:
                await message.delete()
                notice = await message.channel.send(f"🔗 <@{message.author.id}> لینک لەم کەناڵەدا ڕێگەپێنەدراوە.")
                await asyncio.sleep(5)
                await notice.delete()
            except discord.HTTPException:
                pass
            return

    # 5 messages in 7 seconds = spam
    if bot.store.get_bool(message.guild.id, "antispam") and not message.author.guild_permissions.administrator:
        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        q = bot.spam[key]
        q.append(now)
        while q and now - q[0] > 7:
            q.popleft()
        if len(q) >= 5:
            try:
                await message.delete()
                await message.channel.send(f"🛡️ <@{message.author.id}> تکایە سپام مەکە.", delete_after=5)
            except discord.HTTPException:
                pass
            return


    await bot.process_commands(message)

app = Flask(__name__)

@app.get("/")
def root():
    return "HMB GLOBAL is active and running!", 200

@app.get("/health")
def health():
    return jsonify(status="online", bot="HMB GLOBAL", uptime=time.time() - bot.started), 200

def run_web():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("TOKEN is missing from Railway Variables!")
    Thread(target=run_web, daemon=True).start()
    bot.run(TOKEN, log_handler=None)
