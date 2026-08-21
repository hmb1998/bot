import os
import time
import asyncio
import logging
import random
import re
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
PREFIX = os.getenv("PREFIX", "$")
PORT = int(os.getenv("PORT", "3000"))
OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
REGISTER_COMMANDS = os.getenv("REGISTER_COMMANDS", "true").lower() == "true"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("HMB_GLOBAL")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.messages = True
intents.voice_states = True
intents.reactions = True

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

    if message.content.startswith(PREFIX):
        parts = message.content[len(PREFIX):].strip().split(maxsplit=1)
        if parts:
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            if cmd == "ping":
                await message.channel.send(f"🏓 Pong! API: {round(bot.latency * 1000)} ms")
                return
            if cmd == "help":
                names = sorted(c.name for c in bot.tree.get_commands())
                await message.channel.send(("📚 Commands:\n" + " • ".join(f"`{x}`" for x in names))[:4000])
                return
            if cmd == "uptime":
                sec = int(time.time() - bot.started)
                await message.channel.send(f"⏱️ {sec//3600}h {(sec%3600)//60}m {sec%60}s")
                return
            if cmd == "coinflip":
                await message.channel.send(f"🪙 **{random.choice(['Heads', 'Tails'])}**")
                return
            if cmd == "roll":
                try:
                    mx = int(arg or "100")
                except ValueError:
                    mx = 100
                await message.channel.send(f"🎲 {random.randint(1, max(1, min(mx, 100000)))}")
                return
            if cmd == "say" and message.author.guild_permissions.manage_messages and arg:
                await message.channel.send(arg)
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
