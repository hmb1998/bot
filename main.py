import os, json, time, asyncio, logging, random, re, platform
from pathlib import Path
from collections import defaultdict, deque
from threading import Thread

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask, jsonify

from music import MusicManager, setup_music_commands
from moderation import setup_moderation
from features import setup_features

load_dotenv()
BASE=Path(__file__).parent
TOKEN=os.getenv("TOKEN","").strip()
PREFIX=os.getenv("PREFIX","$")
PORT=int(os.getenv("PORT","3000"))
OWNER_ID=int(os.getenv("OWNER_ID","0") or 0)
REGISTER_COMMANDS=os.getenv("REGISTER_COMMANDS","true").lower()=="true"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log=logging.getLogger("HMB_GLOBAL")

intents=discord.Intents.default()
intents.guilds=True
intents.members=True
intents.message_content=True
intents.messages=True
intents.voice_states=True
intents.reactions=True

class HMBGlobal(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)
        self.music=MusicManager(self)
        self.spam=defaultdict(deque)
        self.started=time.time()
        self.prefix_commands=[]
        self.dynamic_slash=[]

    async def setup_hook(self):
        setup_moderation(self)
        setup_features(self)
        setup_music_commands(self)
        await self.load_all_commands()
        if REGISTER_COMMANDS:
            try:
                synced=await self.tree.sync()
                log.info("Registered %d GLOBAL slash commands", len(synced))
            except Exception:
                log.exception("Slash command registration failed")

    async def load_all_commands(self):
        # Commands from the original JS project are represented in command_manifest.json.
        # Important commands have native Python implementations; remaining commands get a
        # safe informational handler so no command silently disappears.
        manifest=json.loads((BASE/'command_manifest.json').read_text(encoding='utf-8'))
        implemented=set(self.tree.get_commands()[i].name for i in range(len(self.tree.get_commands())))
        for item in manifest:
            name=item['name']
            if name in implemented or name in self.dynamic_slash: continue
            async def callback(interaction: discord.Interaction, _name=name):
                await interaction.response.send_message(
                    f"⚠️ `$ {_name}` ئەم command ـە لە وەشانی Python ـدا هێشتا implementation ـی تایبەتی نییە. ", ephemeral=True)
            callback.__name__=f"cmd_{name}"
            try:
                cmd=app_commands.Command(name=name, description=item['description'] or name, callback=callback)
                self.tree.add_command(cmd)
                self.dynamic_slash.append(name)
            except Exception as e:
                log.warning("Could not register %s: %s", name, e)

    async def on_ready(self):
        log.info("======================================")
        log.info("HMB GLOBAL IS ONLINE")
        log.info("Logged in as: %s (%s)", self.user, self.user.id)
        log.info("Servers: %d", len(self.guilds))
        log.info("Prefix: %s", PREFIX)
        log.info("Slash Commands: %d", len(self.tree.get_commands()))
        log.info("======================================")
        try:
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="HMB GLOBAL • Music System"), status=discord.Status.online)
        except Exception: pass

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound): return
        log.exception("Prefix command error", exc_info=error)
        try: await ctx.send("❌ هەڵەیەکی نەخوازراو ڕوویدا.")
        except Exception: pass

bot=HMBGlobal()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    # Link protection from original project
    try:
        cfg=json.loads((BASE/'links.json').read_text()) if (BASE/'links.json').exists() else {}
        enabled=bool(cfg.get(str(message.guild.id),{}).get('enabled',cfg.get('enabled',False)))
        if enabled and not message.author.guild_permissions.administrator and re.search(r'(?:https?://|www\.)\S+',message.content,re.I):
            await message.delete()
            notice=await message.channel.send(f"🔗 <@{message.author.id}> لینک لەم کەناڵەدا ڕێگەپێدراو نییە.")
            await asyncio.sleep(5); await notice.delete()
            return
    except Exception: pass
    # Anti-spam: original uses a 7 second window
    try:
        cfg=json.loads((BASE/'antispam.json').read_text()) if (BASE/'antispam.json').exists() else {'enabled':False}
        if cfg.get('enabled') and not message.author.guild_permissions.administrator:
            key=(message.guild.id,message.author.id); now=time.monotonic(); q=bot.spam[key]; q.append(now)
            while q and now-q[0]>7: q.popleft()
            if len(q)>=5:
                try: await message.delete()
                except Exception: pass
                try: await message.channel.send(f"🛡️ <@{message.author.id}> تکایە سپام مەکە.", delete_after=5)
                except Exception: pass
                return
    except Exception: pass
    # Prefix `$` commands: mirror the main commands for the most-used operations.
    if message.content.startswith(PREFIX):
        parts=message.content[len(PREFIX):].strip().split(maxsplit=1)
        if parts:
            cmd=parts[0].lower(); arg=parts[1] if len(parts)>1 else ''
            if cmd=='ping':
                await message.channel.send(f"🏓 Pong! API: {round(bot.latency*1000)} ms"); return
            if cmd=='help':
                names=sorted(c.name for c in bot.tree.get_commands()); await message.channel.send(('📚 Commands:\n'+' • '.join(f'`{x}`' for x in names))[:4000]); return
            if cmd=='uptime':
                sec=int(time.time()-bot.started); await message.channel.send(f"⏱️ Uptime: {sec//3600}h {(sec%3600)//60}m {sec%60}s"); return
            if cmd=='coinflip':
                await message.channel.send(f"🪙 **{random.choice(['Heads','Tails'])}**"); return
            if cmd=='roll':
                try: mx=int(arg or '100')
                except: mx=100
                await message.channel.send(f"🎲 {random.randint(1,max(1,min(mx,100000)))}"); return
            if cmd=='say' and message.author.guild_permissions.manage_messages:
                if arg: await message.channel.send(arg); return
    await bot.process_commands(message)

# Railway keep-alive
app=Flask(__name__)
@app.get('/')
def root(): return 'HMB GLOBAL is active and running 24/7!',200
@app.get('/health')
def health(): return jsonify(status='online',bot='HMB GLOBAL',uptime=time.time()-bot.started),200

def run_web(): app.run(host='0.0.0.0',port=PORT,debug=False,use_reloader=False)

if __name__=='__main__':
    if not TOKEN:
        raise SystemExit('TOKEN is missing from Railway Variables!')
    Thread(target=run_web,daemon=True).start()
    bot.run(TOKEN, log_handler=None)
