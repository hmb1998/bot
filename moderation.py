import discord
from discord import app_commands
from discord.ext import commands

def setup_moderation(bot):
    @bot.tree.command(name='ping',description='بۆ پشکنینی خێرایی و پەیوەندی بۆت')
    async def ping(interaction): await interaction.response.send_message(f'🏓 Pong! API: {round(bot.latency*1000)} ms')
    @bot.tree.command(name='ban',description='قەدەغەکردنی ئەندامێک لە سێروەر')
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(user='ئەندام',reason='هۆکار')
    async def ban(interaction,user:discord.Member,reason:str='هیچ هۆکارێک نەنووسراوە'):
        if not user.bannable: return await interaction.response.send_message('❌ ناتوانم ئەم ئەندامە ban بکەم.',ephemeral=True)
        await user.ban(reason=reason); await interaction.response.send_message(f'🔨 **{user}** ban کرا.\n📝 {reason}')
    @bot.tree.command(name='kick',description='دەرکردنی ئەندام')
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(interaction,user:discord.Member,reason:str='هیچ هۆکارێک نەنووسراوە'):
        if not user.kickable: return await interaction.response.send_message('❌ ناتوانم kick بکەم.',ephemeral=True)
        await user.kick(reason=reason); await interaction.response.send_message(f'👢 **{user}** kick کرا.')
    @bot.tree.command(name='clear',description='سڕینەوەی پەیامەکان')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(interaction,amount:int):
        if not 1<=amount<=100: return await interaction.response.send_message('❌ ژمارەکە 1-100 بێت.',ephemeral=True)
        await interaction.response.defer(ephemeral=True); n=await interaction.channel.purge(limit=amount); await interaction.followup.send(f'🧹 {len(n)} پەیام سڕایەوە.',ephemeral=True)
    @bot.tree.command(name='slowmode',description='دانانی slowmode')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(interaction,seconds:int):
        await interaction.channel.edit(slowmode_delay=max(0,min(21600,seconds))); await interaction.response.send_message(f'🐢 Slowmode: {seconds}s')
    @bot.tree.command(name='lock',description='داخستنی کەناڵ')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role,send_messages=False); await interaction.response.send_message('🔒 کەناڵ داخرا.')
    @bot.tree.command(name='unlock',description='کردنەوەی کەناڵ')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(interaction):
        await interaction.channel.set_permissions(interaction.guild.default_role,send_messages=None); await interaction.response.send_message('🔓 کەناڵ کرایەوە.')
    @bot.tree.command(name='say',description='ناردنی پەیام بە ناوی بۆت')
    @app_commands.checks.has_permissions(manage_messages=True)
    async def say(interaction,message:str): await interaction.response.send_message(message)
    @bot.tree.command(name='serverinfo',description='زانیاری سێروەر')
    async def serverinfo(interaction):
        g=interaction.guild; await interaction.response.send_message(f'🏠 **{g.name}**\n👥 Members: {g.member_count}\n🆔 {g.id}\n📅 Created: {g.created_at:%Y-%m-%d}')
    @bot.tree.command(name='userinfo',description='زانیاری بەکارهێنەر')
    async def userinfo(interaction,user:discord.Member=None):
        u=user or interaction.user; await interaction.response.send_message(f'👤 **{u}**\n🆔 `{u.id}`\n📅 Joined: {u.joined_at.strftime("%Y-%m-%d") if u.joined_at else "?"}')
    @bot.tree.command(name='nick',description='گۆڕینی nickname')
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nick(interaction,user:discord.Member,nickname:str=None): await user.edit(nick=nickname); await interaction.response.send_message('✅ Nickname گۆڕدرا.')

    @bot.tree.command(name='role',description='زیادکردنی role')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role(interaction,user:discord.Member,role:discord.Role): await user.add_roles(role); await interaction.response.send_message(f'✅ {role.mention} زیادکرا بۆ {user.mention}.')
    @bot.tree.command(name='removerole',description='لابردنی role')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def removerole(interaction,user:discord.Member,role:discord.Role): await user.remove_roles(role); await interaction.response.send_message('✅ Role لابرا.')
    @bot.tree.command(name='mute',description='timeout کردنی ئەندام')
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(interaction,user:discord.Member,minutes:int=10): await user.timeout(discord.utils.utcnow()+__import__('datetime').timedelta(minutes=minutes)); await interaction.response.send_message(f'🔇 {user.mention} بۆ {minutes} خولەک mute کرا.')
    @bot.tree.command(name='unmute',description='لابردنی timeout')
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(interaction,user:discord.Member): await user.timeout(None); await interaction.response.send_message(f'🔊 {user.mention} unmute کرا.')
    @bot.tree.command(name='warn',description='ئاگادارکردنەوەی ئەندام')
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(interaction,user:discord.Member,reason:str='هیچ هۆکارێک نییە'): await interaction.response.send_message(f'⚠️ {user.mention} warn کرا.\n📝 {reason}')

    @bot.tree.error
    async def on_app_error(interaction,error):
        msg='❌ ڕێگەت پێنەدراوە.' if isinstance(error,app_commands.MissingPermissions) else '❌ هەڵەیەکی نەخوازراو ڕوویدا.'
        if interaction.response.is_done(): await interaction.followup.send(msg,ephemeral=True)
        else: await interaction.response.send_message(msg,ephemeral=True)
