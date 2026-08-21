from datetime import timedelta
import discord
from discord import app_commands

def setup_moderation(bot):
    @bot.tree.command(name="ping",description="پشکنینی خێرایی")
    async def ping(interaction: discord.Interaction): await interaction.response.send_message(f"🏓 Pong! API: {round(bot.latency*1000)} ms")

    @bot.tree.command(name="ban",description="قەدەغەکردنی ئەندام")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(interaction: discord.Interaction,user: discord.Member,reason: str="هیچ هۆکارێک نییە"):
        if not user.bannable: return await interaction.response.send_message("❌ ناتوانم ban بکەم.",ephemeral=True)
        await user.ban(reason=reason); await interaction.response.send_message(f"🔨 {user} ban کرا.")

    @bot.tree.command(name="kick",description="دەرکردنی ئەندام")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(interaction: discord.Interaction,user: discord.Member,reason: str="هیچ هۆکارێک نییە"):
        if not user.kickable: return await interaction.response.send_message("❌ ناتوانم kick بکەم.",ephemeral=True)
        await user.kick(reason=reason); await interaction.response.send_message(f"👢 {user} kick کرا.")

    @bot.tree.command(name="clear",description="سڕینەوەی پەیامەکان")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(interaction: discord.Interaction,amount: int):
        if not 1<=amount<=100: return await interaction.response.send_message("❌ 1-100.",ephemeral=True)
        await interaction.response.defer(ephemeral=True); n=await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 {len(n)} پەیام سڕایەوە.",ephemeral=True)

    @bot.tree.command(name="slowmode",description="دانانی slowmode")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(interaction: discord.Interaction,seconds: int):
        await interaction.channel.edit(slowmode_delay=max(0,min(21600,seconds))); await interaction.response.send_message(f"🐢 {seconds}s")

    @bot.tree.command(name="lock",description="داخستنی کەناڵ")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role,send_messages=False); await interaction.response.send_message("🔒 کەناڵ داخرا.")

    @bot.tree.command(name="unlock",description="کردنەوەی کەناڵ")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(interaction: discord.Interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role,send_messages=None); await interaction.response.send_message("🔓 کەناڵ کرایەوە.")

    @bot.tree.command(name="say",description="ناردنی پەیام بە ناوی بۆت")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(interaction: discord.Interaction,message: str): await interaction.response.send_message(message)

    @bot.tree.command(name="serverinfo",description="زانیاری سێروەر")
    async def serverinfo(interaction: discord.Interaction):
        g=interaction.guild; await interaction.response.send_message(f"🏠 **{g.name}**\n👥 Members: {g.member_count}\n🆔 {g.id}\n📅 {g.created_at:%Y-%m-%d}")

    @bot.tree.command(name="userinfo",description="زانیاری بەکارهێنەر")
    async def userinfo(interaction: discord.Interaction,user: discord.Member=None):
        u=user or interaction.user; joined=u.joined_at.strftime("%Y-%m-%d") if u.joined_at else "?"; await interaction.response.send_message(f"👤 **{u}**\n🆔 `{u.id}`\n📅 Joined: {joined}")

    @bot.tree.command(name="nick",description="گۆڕینی nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(interaction: discord.Interaction,user: discord.Member,nickname: str=None):
        await user.edit(nick=nickname); await interaction.response.send_message("✅ Nickname گۆڕدرا.")

    @bot.tree.command(name="nickname",description="گۆڕینی nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nickname(interaction: discord.Interaction,user: discord.Member,nickname: str=None):
        await user.edit(nick=nickname); await interaction.response.send_message("✅ Nickname گۆڕدرا.")

    @bot.tree.command(name="role",description="زیادکردنی role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role(interaction: discord.Interaction,user: discord.Member,role: discord.Role):
        await user.add_roles(role); await interaction.response.send_message(f"✅ {role.mention} زیادکرا.")

    @bot.tree.command(name="removerole",description="لابردنی role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removerole(interaction: discord.Interaction,user: discord.Member,role: discord.Role):
        await user.remove_roles(role); await interaction.response.send_message("✅ Role لابرا.")

    @bot.tree.command(name="mute",description="Timeout کردنی ئەندام")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(interaction: discord.Interaction,user: discord.Member,minutes: int=10):
        await user.timeout(discord.utils.utcnow()+timedelta(minutes=max(1,min(minutes,40320)))); await interaction.response.send_message(f"🔇 {user.mention} mute کرا.")

    @bot.tree.command(name="unmute",description="لابردنی timeout")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(interaction: discord.Interaction,user: discord.Member):
        await user.timeout(None); await interaction.response.send_message(f"🔊 {user.mention} unmute کرا.")

    @bot.tree.command(name="warn",description="ئاگادارکردنەوە")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(interaction: discord.Interaction,user: discord.Member,reason: str="هیچ هۆکارێک نییە"):
        bot.store.add_warning(interaction.guild.id,user.id,reason); await interaction.response.send_message(f"⚠️ {user.mention} warn کرا.")

    @bot.tree.command(name="warnings",description="پیشاندانی ئاگادارکردنەوەکان")
    async def warnings(interaction: discord.Interaction,user: discord.Member=None):
        u=user or interaction.user; rows=bot.store.warnings(interaction.guild.id,u.id)
        text="\n".join(f"{i+1}. {r[0]} — {r[1]}" for i,r in enumerate(rows)) or "هیچ warning نییە."
        await interaction.response.send_message(f"⚠️ Warnings بۆ {u.mention}:\n{text}"[:4000])

    @bot.tree.command(name="clearwarns",description="سڕینەوەی هەموو warnings")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def clearwarns(interaction: discord.Interaction,user: discord.Member):
        bot.store.clear_warnings(interaction.guild.id,user.id); await interaction.response.send_message("✅ هەموو warnings سڕانەوە.")

    @bot.tree.command(name="unwarn",description="لابردنی دوایین warning")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unwarn(interaction: discord.Interaction,user: discord.Member):
        ok=bot.store.remove_last_warning(interaction.guild.id,user.id); await interaction.response.send_message("✅ دوایین warning لابرا." if ok else "❌ warning نەدۆزرایەوە.")

    @bot.tree.command(name="unban",description="لابردنی ban بە ID")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(interaction: discord.Interaction,user_id: str):
        try: uid=int(user_id); await interaction.guild.unban(discord.Object(id=uid))
        except Exception: return await interaction.response.send_message("❌ Unban نەکرا.",ephemeral=True)
        await interaction.response.send_message("✅ Unban کرا.")

    @bot.tree.error
    async def on_app_error(interaction,error):
        msg="❌ ڕێگەت پێنەدراوە." if isinstance(error,app_commands.MissingPermissions) else "❌ هەڵەیەکی نەخوازراو ڕوویدا."
        if interaction.response.is_done(): await interaction.followup.send(msg,ephemeral=True)
        else: await interaction.response.send_message(msg,ephemeral=True)
