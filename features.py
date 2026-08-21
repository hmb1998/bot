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
        isinstance(n, ast.Constant) and (not isinstance(n.value, (int, float)) or isinstance(n.value, bool))
        for n in ast.walk(tree)
    ):
        raise ValueError

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.UnaryOp):
            return {ast.USub: operator.neg, ast.UAdd: operator.pos}[type(n.op)](ev(n.operand))
        if isinstance(n, ast.BinOp):
            fn = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                  ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
                  ast.Mod: operator.mod, ast.Pow: operator.pow}[type(n.op)]
            return fn(ev(n.left), ev(n.right))
        raise ValueError

    result = ev(tree)
    if abs(result) > 10**100:
        raise ValueError
    return result


def setup_features(bot):
    @bot.tree.command(name="antispam", description="دژەسپام: چالاک/ناچالاک/دۆخ")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(action="on / off / status")
    async def antispam(interaction: discord.Interaction, action: str):
        a = action.lower()
        if a in ("on", "off"):
            bot.store.set(interaction.guild.id, "antispam", a == "on")
        state = bot.store.get_bool(interaction.guild.id, "antispam")
        await interaction.response.send_message(
            f"🛡️ **Anti-Spam:** {'چالاکە ✅' if state else 'ناچالاکە ❌'}\n"
            "⚡ سپام بەخێرایی دەناسێتەوە، پەیامەکانی سپامر دەسڕێتەوە و 10 خولەک Timeout دەکات.",
            ephemeral=True,
        )

    @bot.tree.command(name="link", description="ڕێکخستنی Link Guard")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(action="on / off / status")
    async def link(interaction: discord.Interaction, action: str):
        if action.lower() in ("on", "off"):
            bot.store.set(interaction.guild.id, "link_protection", action.lower() == "on")
        state = bot.store.get_bool(interaction.guild.id, "link_protection")
        await interaction.response.send_message(
            f"🔗 **Link Guard:** {'چالاکە ✅' if state else 'ناچالاکە ❌'}", ephemeral=True
        )

    @bot.tree.command(name="botstats", description="ئاماری بۆت")
    async def botstats(interaction: discord.Interaction):
        await interaction.response.send_message(
            f"🤖 **HMB GLOBAL**\n🏠 Servers: {len(bot.guilds)}\n"
            f"📡 Ping: {round(bot.latency * 1000)}ms\n🐍 Python 3.12\n"
            "⌨️ `/help` یان `$help`"
        )

    @bot.tree.command(name="uptime", description="کاتی کارکردنی بۆت")
    async def uptime(interaction: discord.Interaction):
        sec = int(time.time() - bot.started)
        await interaction.response.send_message(f"⏱️ Uptime: {sec//3600}h {(sec%3600)//60}m {sec%60}s")

    @bot.tree.command(name="coinflip", description="سکە هەڵدان")
    async def coinflip(interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 **{random.choice(['Heads', 'Tails'])}**")

    @bot.tree.command(name="roll", description="ژمارە هەڵبژێرە")
    async def roll(interaction: discord.Interaction, max_value: int = 100):
        await interaction.response.send_message(f"🎲 {random.randint(1, max(1, min(max_value, 100000)))}")

    @bot.tree.command(name="invite", description="لینکی بانگهێشت")
    async def invite(interaction: discord.Interaction):
        await interaction.response.send_message(
            f"https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot%20applications.commands&permissions=8"
        )

    @bot.tree.command(name="avatar", description="پیشاندانی avatar")
    async def avatar(interaction: discord.Interaction, user: discord.User = None):
        await interaction.response.send_message((user or interaction.user).display_avatar.url)

    @bot.tree.command(name="help", description="مێنوی جوانی هەموو فەرمانەکان")
    async def help_cmd(interaction: discord.Interaction):
        music = {"play", "search", "spotify", "join", "leave", "pause", "resume", "skip", "stop", "queue", "shuffle", "nowplaying", "clearqueue", "remove", "volume", "loop", "mazensido", "azar"}
        moderation = {"ping", "ban", "kick", "clear", "slowmode", "lock", "unlock", "say", "nick", "nickname", "role", "removerole", "mute", "unmute", "warn", "warnings", "clearwarns", "unwarn", "unban", "purgebots", "purgehumans", "nuke", "antispam", "link", "setlogs"}
        management = {"control", "ticket", "add", "close", "autorole", "welcome", "giveaway", "refresh", "owner"}
        info = {"serverinfo", "userinfo", "roles", "servericon", "serverbanner", "banner", "rank", "botstats", "uptime", "debug", "invite", "avatar"}
        tools = {"calculator", "ascii", "poll", "quiz", "ship", "coinflip", "roll"}

        available = sorted(c.name for c in bot.tree.get_commands() if isinstance(c, app_commands.Command))
        known = music | moderation | management | info | tools | {"help"}
        extra = [name for name in available if name not in known]

        def line(title, names):
            names = sorted(set(names) & set(available))
            return f"{title}\n" + ("  ".join(f"`/{n}`" for n in names) if names else "—")

        embed = discord.Embed(
            title="🤖 HMB GLOBAL • COMMAND CENTER",
            description=(
                "✨ **Dual Control:** هەموو command ـەکان بە هەردوو شێواز کار دەکەن:\n"
                "`/command`  •  `$command`\n\n"
                + line("🎵 **MUSIC & PLAYER**", music) + "\n\n"
                + line("🛡️ **MODERATION & SECURITY**", moderation) + "\n\n"
                + line("🎫 **SERVER & MANAGEMENT**", management) + "\n\n"
                + line("👤 **INFO & PROFILE**", info) + "\n\n"
                + line("🎮 **FUN & TOOLS**", tools)
                + (f"\n\n🧩 **OTHER**\n{'  '.join(f'`/{n}`' for n in sorted(extra))}" if extra else "")
                + "\n\n🎛️ **CONTROL CENTER**\n`/control` یان `$control` → Search، Queue، Skip، Volume، Loop، Anti-Spam و Link Guard هەمووی لە یەک شوێن."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"HMB GLOBAL • {len(available)} commands • /command + $command")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="calculator", description="ژمێریاری")
    async def calculator(interaction: discord.Interaction, expression: str):
        try:
            result = safe_calc(expression)
        except Exception:
            return await interaction.response.send_message("❌ Expression ڕێگەپێنەدراوە.", ephemeral=True)
        await interaction.response.send_message(f"🧮 `{expression}` = **{result}**")
