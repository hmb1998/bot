import asyncio, os, re, logging, discord
import yt_dlp
from discord.ext import commands
from discord import app_commands

YDL_OPTS={'format':'bestaudio/best','noplaylist':True,'quiet':True,'default_search':'ytsearch1','extract_flat':False}
FFMPEG_OPTS={'before_options':'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options':'-vn'}

class Track:
    def __init__(self,title,url,webpage=None): self.title=title; self.url=url; self.webpage=webpage or url

class MusicManager:
    def __init__(self,bot): self.bot=bot; self.queues={}; self.current={}; self.voice={}; self.loop={}
    async def extract(self,query):
        loop=asyncio.get_running_loop()
        def work():
            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                info=ydl.extract_info(query,download=False)
                if 'entries' in info: info=next(iter(info['entries']))
                return Track(info.get('title',query),info.get('url') or info.get('webpage_url'),info.get('webpage_url'))
        return await loop.run_in_executor(None,work)
    async def ensure_voice(self,interaction):
        if not interaction.guild: return None
        vc=interaction.guild.voice_client
        target=interaction.user.voice.channel if interaction.user.voice else None
        if not target: return None
        if vc and vc.channel!=target: await vc.move_to(target)
        elif not vc: vc=await target.connect()
        self.voice[interaction.guild.id]=vc; return vc
    async def play_next(self,guild_id):
        vc=self.voice.get(guild_id)
        q=self.queues.setdefault(guild_id,deque())
        current=self.current.get(guild_id)

        if not vc:
            return

        # Loop the current track when enabled; otherwise take the next queued track.
        if self.loop.get(guild_id) and current:
            track=current
        elif q:
            track=q.popleft()
            self.current[guild_id]=track
        else:
            self.current.pop(guild_id, None)
            return

        def after(err):
            if err:
                logging.getLogger("HMB_GLOBAL").error("FFmpeg playback error: %s", err)
            asyncio.run_coroutine_threadsafe(
                self.play_next(guild_id), self.bot.loop
            )

        source=discord.FFmpegPCMAudio(track.url,**FFMPEG_OPTS)
        vc.play(source,after=after)

# import here to avoid extra dependency in main
from collections import deque

def setup_music_commands(bot):
    @bot.tree.command(name='play',description='لێدانی گۆرانی بە ناونیشان یان لینک')
    @app_commands.describe(song='ناوی گۆرانی یان لینکی یوتیوب')
    async def play(interaction:discord.Interaction,song:str):
        vc=await bot.music.ensure_voice(interaction)
        if not vc: return await interaction.response.send_message('❌ تکایە سەرەتا بچۆ ناو کەناڵێکی دەنگییەوە.',ephemeral=True)
        await interaction.response.defer()
        try:
            track=await bot.music.extract(song); bot.music.queues.setdefault(interaction.guild.id,deque()).append(track)
            if not vc.is_playing(): await bot.music.play_next(interaction.guild.id)
            await interaction.followup.send(f'🎵 دەنگپەخشکرا: **{track.title}**')
        except Exception as e: await interaction.followup.send(f'❌ نەتوانرا گۆرانی پەخش بکرێت. `{e}`',ephemeral=True)

    @bot.tree.command(name='join',description='چوونە ناو voice channel')
    async def join(interaction):
        vc=await bot.music.ensure_voice(interaction); await interaction.response.send_message('✅ پەیوەندی بە voice کرا.' if vc else '❌ لە voice channel نییت.',ephemeral=True)
    @bot.tree.command(name='leave',description='دەرچوون لە voice channel')
    async def leave(interaction):
        vc=interaction.guild.voice_client if interaction.guild else None
        if vc: await vc.disconnect(force=True)
        bot.music.voice.pop(interaction.guild.id,None); await interaction.response.send_message('👋 دەرچووم لە voice.')
    @bot.tree.command(name='pause',description='وەستاندنی گۆرانی')
    async def pause(interaction):
        vc=interaction.guild.voice_client if interaction.guild else None
        if vc and vc.is_playing(): vc.pause(); return await interaction.response.send_message('⏸️ وەستێنرا.')
        await interaction.response.send_message('❌ هیچ گۆرانییەک لە پەخشکردندا نییە.',ephemeral=True)
    @bot.tree.command(name='resume',description='دەستپێکردنەوەی گۆرانی')
    async def resume(interaction):
        vc=interaction.guild.voice_client if interaction.guild else None
        if vc and vc.is_paused(): vc.resume(); return await interaction.response.send_message('▶️ بەردەوام بوو.')
        await interaction.response.send_message('❌ گۆرانی وەستاندراو نییە.',ephemeral=True)
    @bot.tree.command(name='skip',description='تێپەڕاندنی گۆرانی')
    async def skip(interaction):
        vc=interaction.guild.voice_client if interaction.guild else None
        if vc and (vc.is_playing() or vc.is_paused()): vc.stop(); return await interaction.response.send_message('⏭️ Skip کرا.')
        await interaction.response.send_message('❌ هیچ گۆرانییەک نییە.',ephemeral=True)
    @bot.tree.command(name='stop',description='وەستاندن و پاککردنەوەی queue')
    async def stop(interaction):
        vc=interaction.guild.voice_client if interaction.guild else None
        if vc: vc.stop()
        bot.music.queues[interaction.guild.id]=deque(); await interaction.response.send_message('⏹️ پەخشکردن و queue وەستاندرا.')
    @bot.tree.command(name='queue',description='بینینی queue')
    async def queue(interaction):
        q=bot.music.queues.get(interaction.guild.id,deque()); cur=bot.music.current.get(interaction.guild.id)
        text=f'🎵 ئێستا: **{cur.title}**\n' if cur else ''
        text+='\n'.join(f'{i+1}. {x.title}' for i,x in enumerate(q)) or 'Queue بەتاڵە.'
        await interaction.response.send_message(text[:4000])
    @bot.tree.command(name='volume',description='گۆڕینی دەنگ')
    @app_commands.describe(value='0-100')
    async def volume(interaction,value:int):
        if not 0<=value<=100: return await interaction.response.send_message('❌ ژمارەکە دەبێت 0 تا 100 بێت.',ephemeral=True)
        await interaction.response.send_message(f'🔊 Volume بۆ {value}% دانرا. (FFmpeg source ـی ئێستا بەبێ restart volume control ـی ناوخۆیی نییە.)',ephemeral=True)
    @bot.tree.command(name='loop',description='دووبارەکردنەوەی گۆرانی')
    async def loop(interaction):
        gid=interaction.guild.id; bot.music.loop[gid]=not bot.music.loop.get(gid,False); await interaction.response.send_message(f"🔁 Loop: {'ON' if bot.music.loop[gid] else 'OFF'}")

# commands are installed from main setup
