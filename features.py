import ast, operator, random, time
from collections import defaultdict, deque
from datetime import timedelta
import discord
from discord import app_commands

def safe_calc(expression: str):
    if len(expression) > 100:
        raise ValueError
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div,
               ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Constant, ast.FloorDiv)
    tree = ast.parse(expression, mode="eval")
    if any(type(n) not in allowed for n in ast.walk(tree)) or any(
        isinstance(n, ast.Constant) and (not isinstance(n.value, (int,float)) or isinstance(n.value,bool))
        for n in ast.walk(tree)):
        raise ValueError
    def ev(n):
        if isinstance(n, ast.Expression): return ev(n.body)
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.UnaryOp): return {ast.USub:operator.neg, ast.UAdd:operator.pos}[type(n.op)](ev(n.operand))
        if isinstance(n, ast.BinOp):
            fn={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,
                ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}[type(n.op)]
            return fn(ev(n.left),ev(n.right))
        raise ValueError
    result=ev(tree)
    if abs(result) > 10**100: raise ValueError
    return result

def setup_features(bot):
    # Second-layer anti-spam: duplicate messages, mention floods, long floods
    # and high-frequency bursts. The main handler keeps its basic limiter too.
    spam_windows = defaultdict(deque)
    last_text = {}
    duplicate_count = defaultdict(int)
    cooldown = {}

    @bot.listen("on_message")
    async def hmb_strong_antispam(message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not bot.store.get_bool(message.guild.id, "antispam"):
            return
        if message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages:
            return

        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        q = spam_windows[key]
        q.append(now)
        while q and now - q[0] > 10:
            q.popleft()

        normalized = " ".join(message.content.lower().split())[:300]
        if normalized and normalized == last_text.get(key):
            duplicate_count[key] += 1
        else:
            duplicate_count[key] = 1
            last_text[key] = normalized

        too_fast = len(q) >= 8
        repeated = duplicate_count[key] >= 3
        mention_spam = len(message.mentions) + len(message.role_mentions) >= 5
        content_flood = len(message.content) >= 1500
        if not (too_fast or repeated or mention_spam or content_flood):
            return
        if now < cooldown.get(key, 0):
            return
        cooldown[key] = now + 10

        try:
            await message.delete()
        except discord.HTTPException:
            pass

        try:
            await message.author.timeout(
                discord.utils.utcnow() + timedelta(seconds=60),
                reason="HMB GLOBAL anti-spam"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        try:
            await message.channel.send(
                f"🛡️ {message.author.mention} دژەسپام چالاک بوو؛ تکایە سپام مەکە.",
                delete_after=5,
            )
        except discord.HTTPException:
            pass

    @bot.tree.command(name="antispam", description="چالاککردن یان ناچالاککردنی دژە سپام")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(action="on/off/status")
    async def antispam(interaction: discord.Interaction, action: str):
        a=action.lower()
        if a in ("on","off"): bot.store.set(interaction.guild.id,"antispam",a=="on")
        state=bot.store.get_bool(interaction.guild.id,"antispam")
        await interaction.response.send_message(f"🛡️ Anti-Spam: {'ON ✅' if state else 'OFF ❌'}", ephemeral=True)

    @bot.tree.command(name="link", description="ڕێکخستنی link protection")
    @app_commands.checks.has_permissions(administrator=True)
    async def link(interaction: discord.Interaction, action: str):
        if action.lower() in ("on","off"): bot.store.set(interaction.guild.id,"link_protection",action.lower()=="on")
        state=bot.store.get_bool(interaction.guild.id,"link_protection")
        await interaction.response.send_message(f"🔗 Link protection: {'ON ✅' if state else 'OFF ❌'}", ephemeral=True)

    @bot.tree.command(name="botstats", description="ئاماری بۆت")
    async def botstats(interaction: discord.Interaction):
        await interaction.response.send_message(f"🤖 HMB GLOBAL\n🏠 Servers: {len(bot.guilds)}\n📡 Ping: {round(bot.latency*1000)}ms\n🐍 Python 3.12\n⌨️ Commands: /help و $help")

    @bot.tree.command(name="uptime", description="کاتی کارکردنی بۆت")
    async def uptime(interaction: discord.Interaction):
        sec=int(time.time()-bot.started)
        await interaction.response.send_message(f"⏱️ Uptime: {sec//3600}h {(sec%3600)//60}m {sec%60}s")

    @bot.tree.command(name="coinflip", description="سکە هەڵدان")
    async def coinflip(interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 **{random.choice(['Heads','Tails'])}**")

    @bot.tree.command(name="roll", description="ژمارە هەڵبژێرە")
    async def roll(interaction: discord.Interaction, max_value: int = 100):
        await interaction.response.send_message(f"🎲 {random.randint(1,max(1,min(max_value,100000)))}")

    @bot.tree.command(name="invite", description="لینکی بانگهێشت")
    async def invite(interaction: discord.Interaction):
        await interaction.response.send_message(f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot%20applications.commands&permissions=8")

    @bot.tree.command(name="avatar", description="پیشاندانی avatar")
    async def avatar(interaction: discord.Interaction, user: discord.User = None):
        await interaction.response.send_message((user or interaction.user).display_avatar.url)

    @bot.tree.command(name="help", description="یارمەتی command ـەکان")
    async def help_cmd(interaction: discord.Interaction):
        cmds=sorted(c.name for c in bot.tree.get_commands())
        await interaction.response.send_message(("🤖 HMB GLOBAL — Command Center\n▶️ Slash: `/command`\n⌨️ Prefix: `$command`\n\n📚 Commands:\n"+" • ".join(f"`{x}`" for x in cmds))[:4000], ephemeral=True)

    @bot.tree.command(name="calculator", description="ژمێریاری")
    async def calculator(interaction: discord.Interaction, expression: str):
        try: result=safe_calc(expression)
        except Exception: return await interaction.response.send_message("❌ Expression ڕێگەپێنەدراوە.",ephemeral=True)
        await interaction.response.send_message(f"🧮 `{expression}` = **{result}**")
