import json, re, time, random, asyncio
from pathlib import Path
import discord
from discord import app_commands
BASE=Path(__file__).parent

def jload(name,default):
    p=BASE/name
    try: return json.loads(p.read_text())
    except Exception: return default

def jsave(name,data): (BASE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2))

def setup_features(bot):
    @bot.tree.command(name='antispam',description='چالاککردن یان ناچالاککردنی دژە سپام')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(action='on/off/status')
    async def antispam(interaction,action:str):
        data=jload('antispam.json',{'enabled':False})
        if action.lower()=='on': data['enabled']=True; jsave('antispam.json',data); msg='✅ Anti-Spam چالاک کرا.'
        elif action.lower()=='off': data['enabled']=False; jsave('antispam.json',data); msg='❌ Anti-Spam ناچالاک کرا.'
        else: msg=f"🛡️ Anti-Spam: {'ON ✅' if data.get('enabled') else 'OFF ❌'}"
        await interaction.response.send_message(msg,ephemeral=True)
    @bot.tree.command(name='link',description='ڕێکخستنی link protection')
    @app_commands.checks.has_permissions(administrator=True)
    async def link(interaction,action:str):
        data=jload('links.json',{})
        data['enabled']=action.lower()=='on'; jsave('links.json',data)
        await interaction.response.send_message(f"🔗 Link protection: {'ON ✅' if data['enabled'] else 'OFF ❌'}",ephemeral=True)
    @bot.tree.command(name='botstats',description='ئاماری بۆت')
    async def botstats(interaction): await interaction.response.send_message(f'🤖 HMB GLOBAL\n🏠 Servers: {len(bot.guilds)}\n📡 Ping: {round(bot.latency*1000)}ms\n🐍 Python: 3.x')
    @bot.tree.command(name='uptime',description='کاتی کارکردنی بۆت')
    async def uptime(interaction):
        sec=int(time.time()-bot.started); await interaction.response.send_message(f'⏱️ Uptime: {sec//3600}h {(sec%3600)//60}m {sec%60}s')
    @bot.tree.command(name='coinflip',description='سکە هەڵدان')
    async def coinflip(interaction): await interaction.response.send_message(f'🪙 **{random.choice(["Heads","Tails"])}**')
    @bot.tree.command(name='roll',description='ژمارە هەڵبژێرە')
    async def roll(interaction,max_value:int=100): await interaction.response.send_message(f'🎲 {random.randint(1,max(1,min(max_value,100000)))}')
    @bot.tree.command(name='invite',description='لینکی بانگهێشت')
    async def invite(interaction): await interaction.response.send_message(f'https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot%20applications.commands&permissions=8')
    @bot.tree.command(name='avatar',description='پیشاندانی avatar')
    async def avatar(interaction,user:discord.User=None):
        u=user or interaction.user; await interaction.response.send_message(u.display_avatar.url)
    @bot.tree.command(name='help',description='یارمەتی command ـەکان')
    async def help_cmd(interaction):
        cmds=sorted(c.name for c in bot.tree.get_commands()); await interaction.response.send_message('📚 Commands:\n'+' • '.join(f'`{x}`' for x in cmds)[:4000],ephemeral=True)
    @bot.tree.command(name='calculator',description='ژمێریاری')
    async def calculator(interaction,expression:str):
        if not re.fullmatch(r'[0-9+\-*/(). %]+',expression): return await interaction.response.send_message('❌ Expression ڕێگەپێنەدراوە.',ephemeral=True)
        try: await interaction.response.send_message(f'🧮 `{expression}` = **{eval(expression,{"__builtins__":{}},{})}**')
        except Exception: await interaction.response.send_message('❌ هەڵە لە ژمێریاری.',ephemeral=True)
