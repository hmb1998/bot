import asyncio, random, re, string
from collections import deque
from datetime import timedelta
import discord
from discord import app_commands



class MusicSearchModal(discord.ui.Modal, title="🎵 گەڕانی گۆرانی"):
    query = discord.ui.TextInput(
        label="ناوی گۆرانی یان لینکی گۆرانی",
        placeholder="مثال: Mert Demir - Ateşe Düştüm یان YouTube/Spotify/TikTok URL",
        required=True,
        max_length=500,
    )

    def __init__(self, bot):
        super().__init__(timeout=120)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        query = str(self.query).strip()
        try:
            vc = await self.bot.music.ensure_voice(interaction)
            if not vc:
                return await interaction.response.send_message(
                    "❌ سەرەتا بچۆ ناو Voice Channel.", ephemeral=True
                )
            await interaction.response.defer(ephemeral=True)
            tracks = await self.bot.music.extract(query)
            if not isinstance(tracks, list):
                tracks = [tracks]
            q = self.bot.music.queues.setdefault(interaction.guild.id, deque())
            q.extend(tracks)
            if not vc.is_playing() and not vc.is_paused():
                await self.bot.music.play_next(interaction.guild.id)
            if len(tracks) == 1:
                text = f"✅ **{tracks[0].title}** زیادکرا بۆ Queue و پەخشکردن."
            else:
                text = f"✅ **{len(tracks)}** دانە لە Queue زیادکرا."
            await interaction.followup.send(text, ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(
                f"❌ گەڕان/پەخشکردن سەرکەوتوو نەبوو.\n`{str(exc)[:700]}`",
                ephemeral=True,
            )


class HMBControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=600)
        self.bot = bot

    async def _music(self, interaction, action):
        vc = interaction.guild.voice_client if interaction.guild else None
        gid = interaction.guild.id
        if action == "pause":
            if vc and vc.is_playing():
                vc.pause()
                return await interaction.response.send_message("⏸️ وەستێنرا.", ephemeral=True)
            return await interaction.response.send_message("❌ هیچ گۆرانییەک لە پەخشکردندا نییە.", ephemeral=True)
        if action == "resume":
            if vc and vc.is_paused():
                vc.resume()
                return await interaction.response.send_message("▶️ بەردەوام بوو.", ephemeral=True)
            return await interaction.response.send_message("❌ گۆرانی وەستاندراو نییە.", ephemeral=True)
        if action == "skip":
            if vc and (vc.is_playing() or vc.is_paused()):
                self.bot.music.skip_once.add(gid)
                vc.stop()
                return await interaction.response.send_message("⏭️ Skip کرا.", ephemeral=True)
            return await interaction.response.send_message("❌ هیچ گۆرانییەک نییە.", ephemeral=True)
        if action == "stop":
            self.bot.music.loop[gid] = False
            self.bot.music.skip_once.discard(gid)
            self.bot.music.current.pop(gid, None)
            self.bot.music.queues[gid] = deque()
            if vc:
                vc.stop()
            return await interaction.response.send_message("⏹️ پەخشکردن و Queue وەستاندرا.", ephemeral=True)
        if action == "queue":
            q = self.bot.music.queues.get(gid, deque())
            cur = self.bot.music.current.get(gid)
            text = f"🎵 ئێستا: **{cur.title}**\n" if cur else ""
            text += "\n".join(f"{i + 1}. {x.title}" for i, x in enumerate(q)) or "Queue بەتاڵە."
            return await interaction.response.send_message(text[:1900], ephemeral=True)
        if action == "shuffle":
            q = self.bot.music.queues.get(gid, deque())
            if len(q) < 2:
                return await interaction.response.send_message("❌ بۆ Shuffle کەمتر لە ٢ گۆرانی هەیە.", ephemeral=True)
            items = list(q)
            random.shuffle(items)
            self.bot.music.queues[gid] = deque(items)
            return await interaction.response.send_message("🔀 Queue تێکەڵکرا.", ephemeral=True)
        if action == "clear":
            self.bot.music.queues[gid] = deque()
            return await interaction.response.send_message("🧹 Queue پاککرایەوە.", ephemeral=True)

    async def _volume(self, interaction, value):
        gid = interaction.guild.id
        self.bot.music.volume[gid] = value / 100
        vc = interaction.guild.voice_client
        if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = value / 100
        await interaction.response.send_message(f"🔊 Volume = **{value}%**", ephemeral=True)

    async def _security(self, interaction, key, label):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ تەنها Administrator.", ephemeral=True)
        state = not self.bot.store.get_bool(interaction.guild.id, key)
        self.bot.store.set(interaction.guild.id, key, state)
        await interaction.response.send_message(f"{label}: {'ON ✅' if state else 'OFF ❌'}", ephemeral=True)

    @discord.ui.button(label="گەڕان", emoji="🔎", style=discord.ButtonStyle.primary, row=0)
    async def search_btn(self, interaction, button):
        await interaction.response.send_modal(MusicSearchModal(self.bot))

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary, row=0)
    async def pause_btn(self, interaction, button):
        await self._music(interaction, "pause")

    @discord.ui.button(label="Resume", emoji="▶️", style=discord.ButtonStyle.success, row=0)
    async def resume_btn(self, interaction, button):
        await self._music(interaction, "resume")

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary, row=0)
    async def skip_btn(self, interaction, button):
        await self._music(interaction, "skip")

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger, row=0)
    async def stop_btn(self, interaction, button):
        await self._music(interaction, "stop")

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.secondary, row=1)
    async def queue_btn(self, interaction, button):
        await self._music(interaction, "queue")

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle_btn(self, interaction, button):
        await self._music(interaction, "shuffle")

    @discord.ui.button(label="Clear Queue", emoji="🧹", style=discord.ButtonStyle.danger, row=1)
    async def clear_btn(self, interaction, button):
        await self._music(interaction, "clear")

    @discord.ui.button(label="25%", style=discord.ButtonStyle.secondary, row=1)
    async def vol25_btn(self, interaction, button):
        await self._volume(interaction, 25)

    @discord.ui.button(label="50%", style=discord.ButtonStyle.secondary, row=1)
    async def vol50_btn(self, interaction, button):
        await self._volume(interaction, 50)

    @discord.ui.button(label="75%", style=discord.ButtonStyle.secondary, row=2)
    async def vol75_btn(self, interaction, button):
        await self._volume(interaction, 75)

    @discord.ui.button(label="100%", style=discord.ButtonStyle.secondary, row=2)
    async def vol100_btn(self, interaction, button):
        await self._volume(interaction, 100)

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.primary, row=2)
    async def loop_btn(self, interaction, button):
        gid = interaction.guild.id
        state = not self.bot.music.loop.get(gid, False)
        self.bot.music.loop[gid] = state
        await interaction.response.send_message(f"🔁 Loop: {'ON ✅' if state else 'OFF ❌'}", ephemeral=True)

    @discord.ui.button(label="Now Playing", emoji="🎶", style=discord.ButtonStyle.secondary, row=2)
    async def now_btn(self, interaction, button):
        cur = self.bot.music.current.get(interaction.guild.id)
        if not cur:
            return await interaction.response.send_message("❌ هیچ گۆرانییەک نییە.", ephemeral=True)
        await interaction.response.send_message(f"🎶 **{cur.title}**\n🔗 {cur.webpage}", ephemeral=True)

    @discord.ui.button(label="Anti-Spam", emoji="🛡️", style=discord.ButtonStyle.success, row=3)
    async def antispam_btn(self, interaction, button):
        await self._security(interaction, "antispam", "Anti-Spam")

    @discord.ui.button(label="Link Guard", emoji="🔗", style=discord.ButtonStyle.success, row=3)
    async def link_btn(self, interaction, button):
        await self._security(interaction, "link_protection", "Link Protection")

    @discord.ui.button(label="Status", emoji="📊", style=discord.ButtonStyle.secondary, row=3)
    async def status_btn(self, interaction, button):
        gid = interaction.guild.id
        vc = interaction.guild.voice_client
        cur = self.bot.music.current.get(gid)
        anti = self.bot.store.get_bool(gid, "antispam")
        link = self.bot.store.get_bool(gid, "link_protection")
        await interaction.response.send_message(
            f"🤖 **HMB GLOBAL**\n🎵 Now: **{cur.title if cur else 'None'}**\n"
            f"🔊 Voice: **{'Connected' if vc else 'Disconnected'}**\n"
            f"🛡️ Anti-Spam: **{'ON' if anti else 'OFF'}**\n"
            f"🔗 Link Guard: **{'ON' if link else 'OFF'}**\n"
            "⌨️ `/command` یان `$command`",
            ephemeral=True,
        )

    @discord.ui.button(label="Help", emoji="❓", style=discord.ButtonStyle.secondary, row=3)
    async def help_btn(self, interaction, button):
        await interaction.response.send_message("📚 بۆ هەموو فەرمانەکان `/help` یان `$help` بەکاربهێنە.", ephemeral=True)


def setup_extra_commands(bot):
    @bot.tree.command(name="ascii",description="گۆڕینی دەق بۆ ASCII")
    async def ascii_cmd(interaction: discord.Interaction,text: str):
        # No external ASCII package: safe boxed text.
        out="\n".join(f"│ {c}" for c in text[:30])
        await interaction.response.send_message(f"```text\n┌────────────┐\n{out}\n└────────────┘\n```")

    @bot.tree.command(name="autorole",description="ڕێکخستنی ڕۆڵی خۆکار")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole(interaction: discord.Interaction,role: discord.Role=None):
        if role is None:
            old=bot.store.get_int(interaction.guild.id,"autorole")
            return await interaction.response.send_message(f"🤖 Autorole: `{old}`" if old else "🤖 Autorole دانەنراوە.",ephemeral=True)
        bot.store.set(interaction.guild.id,"autorole",role.id)
        await interaction.response.send_message(f"✅ Autorole = {role.mention}",ephemeral=True)

    @bot.tree.command(name="welcome",description="ڕێکخستنی کەناڵی بەخێرهاتن")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome(interaction: discord.Interaction,channel: discord.TextChannel=None):
        if channel is None:
            bot.store.set(interaction.guild.id,"welcome_channel",0)
            return await interaction.response.send_message("❌ Welcome ناچالاک کرا.",ephemeral=True)
        bot.store.set(interaction.guild.id,"welcome_channel",channel.id)
        await interaction.response.send_message(f"✅ Welcome channel = {channel.mention}",ephemeral=True)

    @bot.tree.command(name="roles",description="پیشاندانی لیستی ڕۆڵەکان")
    async def roles(interaction: discord.Interaction,user: discord.Member=None):
        u=user or interaction.user
        text="\n".join(r.mention for r in u.roles if r.name!=" @everyone") or "هیچ role ـێک نییە."
        await interaction.response.send_message(f"👤 {u.mention}\n{text}"[:4000])

    @bot.tree.command(name="servericon",description="پیشاندانی وێنەی سێروەر")
    async def servericon(interaction: discord.Interaction):
        await interaction.response.send_message(interaction.guild.icon.url if interaction.guild.icon else "❌ سێروەر icon نییە.")

    @bot.tree.command(name="serverbanner",description="پیشاندانی banner سێروەر")
    async def serverbanner(interaction: discord.Interaction):
        await interaction.response.send_message(interaction.guild.banner.url if interaction.guild.banner else "❌ سێروەر banner نییە.")

    @bot.tree.command(name="banner",description="پیشاندانی banner بەکارهێنەر")
    async def banner(interaction: discord.Interaction,user: discord.User=None):
        u=user or interaction.user
        await interaction.response.send_message(u.banner.url if u.banner else "❌ ئەم بەکارهێنەرە banner نییە.")

    @bot.tree.command(name="ship",description="پشکنی ڕێژەی خۆشەویستی")
    async def ship(interaction: discord.Interaction,user1: discord.Member,user2: discord.Member=None):
        user2=user2 or interaction.user
        seed=f"{min(user1.id,user2.id)}:{max(user1.id,user2.id)}:{interaction.guild.id}"
        score=sum(ord(c) for c in seed)%101
        await interaction.response.send_message(f"❤️ {user1.mention} × {user2.mention} = **{score}%**")

    @bot.tree.command(name="rank",description="پیشاندانی ئاست و XP")
    async def rank(interaction: discord.Interaction,user: discord.Member=None):
        u=user or interaction.user; xp=bot.store.add_xp(interaction.guild.id,u.id,0); level=xp//100+1
        await interaction.response.send_message(f"🏆 {u.mention}\nXP: **{xp}**\nLevel: **{level}**")

    @bot.event
    async def on_message_xp(message):
        # Kept as a named helper; main on_message can be extended without a second event.
        return

    @bot.tree.command(name="poll",description="دروستکردنی راپرسی")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def poll(interaction: discord.Interaction,question: str):
        await interaction.response.send_message(f"📊 **Poll:** {question}\n\n👍 = بەڵێ\n👎 = نەخێر")
        msg=await interaction.original_response()
        for emoji in ("👍","👎"):
            try: await msg.add_reaction(emoji)
            except discord.HTTPException: pass

    @bot.tree.command(name="purgebots",description="سڕینەوەی نامەی بۆتەکان")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purgebots(interaction: discord.Interaction,amount: int=100):
        amount=max(1,min(amount,100))
        deleted=await interaction.channel.purge(limit=amount,check=lambda m:m.author.bot)
        await interaction.response.send_message(f"🤖 {len(deleted)} پەیامی bot سڕایەوە.",ephemeral=True)

    @bot.tree.command(name="purgehumans",description="سڕینەوەی نامەی مرۆڤەکان")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purgehumans(interaction: discord.Interaction,amount: int=100):
        amount=max(1,min(amount,100))
        deleted=await interaction.channel.purge(limit=amount,check=lambda m:not m.author.bot)
        await interaction.response.send_message(f"👤 {len(deleted)} پەیامی مرۆڤ سڕایەوە.",ephemeral=True)

    @bot.tree.command(name="nuke",description="نوێکردنەوەی کەناڵ")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def nuke(interaction: discord.Interaction):
        old=interaction.channel
        await interaction.response.send_message("💥 کەناڵ نۆک دەکرێت...",ephemeral=True)
        new=await old.clone(reason=f"Nuke by {interaction.user}")
        await new.edit(position=old.position)
        await old.delete(reason=f"Nuke by {interaction.user}")
        await new.send(f"💥 کەناڵەکە نوێکرایەوە لەلایەن {interaction.user.mention}")

    @bot.tree.command(name="setlogs",description="دیاریکردنی کەناڵی logs")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlogs(interaction: discord.Interaction,channel: discord.TextChannel):
        bot.store.set(interaction.guild.id,"logs_channel",channel.id)
        await interaction.response.send_message(f"✅ Logs = {channel.mention}",ephemeral=True)

    @bot.tree.command(name="debug",description="پشکنینی دۆخی بۆت")
    async def debug(interaction: discord.Interaction):
        vc=interaction.guild.voice_client
        await interaction.response.send_message(f"🐍 Python OK\n📡 Ping: {round(bot.latency*1000)}ms\n🎵 Voice: {'connected' if vc else 'not connected'}")

    @bot.tree.command(name="refresh",description="نوێکردنەوەی slash commands")
    @app_commands.checks.has_permissions(administrator=True)
    async def refresh(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        synced=await bot.tree.sync(guild=interaction.guild)
        await interaction.followup.send(f"✅ {len(synced)} command نوێکرایەوە.",ephemeral=True)

    @bot.tree.command(name="owner",description="فەرمانەکانی خاوەنی بۆت")
    async def owner(interaction: discord.Interaction):
        if bot.owner_id and interaction.user.id != bot.owner_id and interaction.user.id != int(__import__("os").getenv("OWNER_ID","0") or 0):
            return await interaction.response.send_message("❌ تەنها owner.",ephemeral=True)
        await interaction.response.send_message("👑 HMB GLOBAL owner panel: Python edition",ephemeral=True)

    @bot.tree.command(name="add",description="زیادکردنی ئەندام بۆ ناو تیکێت")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def add(interaction: discord.Interaction,user: discord.Member):
        await interaction.channel.set_permissions(user,view_channel=True,send_messages=True)
        await interaction.response.send_message(f"✅ {user.mention} زیادکرا.")

    @bot.tree.command(name="remove",description="دەرکردنی ئەندام لە تیکێت")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def remove(interaction: discord.Interaction,user: discord.Member):
        await interaction.channel.set_permissions(user,view_channel=False)
        await interaction.response.send_message(f"✅ {user.mention} لابرا.")

    @bot.tree.command(name="close",description="داخستنی تیکێتەکە")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def close(interaction: discord.Interaction):
        await interaction.response.send_message("🔒 Ticket داخرا.",ephemeral=True)
        await interaction.channel.set_permissions(interaction.guild.default_role,send_messages=False,reason="Ticket closed")

    @bot.tree.command(name="ticket",description="دروستکردنی تکێت")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket(interaction: discord.Interaction):
        channel=await interaction.guild.create_text_channel(f"ticket-{interaction.user.name}"[:90],reason="HMB ticket")
        await channel.set_permissions(interaction.guild.default_role,view_channel=False)
        await channel.set_permissions(interaction.user,view_channel=True,send_messages=True)
        await interaction.response.send_message(f"🎫 Ticket دروستکرا: {channel.mention}",ephemeral=True)
        await channel.send(f"🎫 {interaction.user.mention} بەخێربێیت. ستاف یارمەتیت دەدات.")

    @bot.tree.command(name="giveaway",description="دەستپێکردنی giveaway")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def giveaway(interaction: discord.Interaction,prize: str,winners: int=1):
        winners=max(1,min(winners,20))
        await interaction.response.send_message(f"🎉 **GIVEAWAY**\n🎁 Prize: **{prize}**\n🏆 Winners: **{winners}**\nReact with 🎉")
        msg=await interaction.original_response()
        await msg.add_reaction("🎉")

    @bot.tree.command(name="quiz",description="یاری پرسیار و وەڵام")
    async def quiz(interaction: discord.Interaction):
        questions=[("پایتختی عێراق چییە؟","baghdad"),("2+2 چەندە؟","4"),("Python چییە؟","programming language")]
        q,a=random.choice(questions)
        await interaction.response.send_message(f"🧠 **Quiz:** {q}\nوەڵام: ||{a}||")

    @bot.tree.command(name="search",description="گەڕان بەدوای گۆرانی")
    async def search(interaction: discord.Interaction,song: str):
        await interaction.response.send_message(f"🔎 گەڕان بۆ: **{song}**\nبۆ پەخشکردن `/play {song}` بەکاربهێنە.")

    @bot.tree.command(name="spotify",description="پەخشکردنی playlist")
    async def spotify(interaction: discord.Interaction,url: str):
        await interaction.response.send_message("🎵 Spotify URL وەرگیرا؛ بۆ یاری لە یوتیوب `/play` بەکاربهێنە.",ephemeral=True)

    @bot.tree.command(name="control",description="کۆنترۆڵی تەواوی موزیک، Queue، Search و دژەسپام")
    async def control(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 HMB GLOBAL • CONTROL CENTER",
            description=(
                "🎵 **MUSIC**\n"
                "🔎 Search بە ناوی گۆرانی یان لینک\n"
                "⏯️ Pause / Resume  •  ⏭️ Skip  •  ⏹️ Stop\n"
                "📜 Queue  •  🔀 Shuffle  •  🧹 Clear Queue  •  🔁 Loop\n"
                "🎶 Now Playing  •  🔊 Volume 25/50/75/100%\n\n"
                "🛡️ **SECURITY**\n"
                "Anti-Spam → سپامر پەیامەکانی لە کەناڵەکە دەسڕێتەوە و **10 خولەک Timeout** دەکات.\n"
                "🔗 Link Guard → کۆنترۆڵی لینکەکان\n\n"
                "⌨️ هەموو فەرمانەکان بە `/command` و `$command` کار دەکەن.\n"
                "✨ دوگمەکانی خوارەوە هەموو کۆنترۆڵە سەرەکییەکانت لە یەک شوێن کۆدەکەنەوە."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="HMB GLOBAL • Smart • Secure • Powerful")
        await interaction.response.send_message(embed=embed, view=HMBControlView(bot))

    @bot.tree.command(name="mazensido",description="مێنوی گۆرانی")
    async def mazensido(interaction: discord.Interaction):
        await interaction.response.send_message("🎵 Mazen menu: `/play` + ناوی گۆرانی")

    @bot.tree.command(name="azar",description="مێنوی گۆرانی")
    async def azar(interaction: discord.Interaction):
        await interaction.response.send_message("🎵 Azar menu: `/play` + ناوی گۆرانی")
