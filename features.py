import ast, operator, random, time, inspect, re
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




# =========================================================
# HELP COMMAND BUTTONS
# =========================================================

_HELP_CATEGORIES = {
    "🎵 MUSIC & PLAYER": {"play", "search", "join", "leave", "pause", "resume", "skip", "stop", "queue", "shuffle", "nowplaying", "clearqueue", "remove", "volume", "loop", "mazensido", "azar"},
    "🛡️ MODERATION & SECURITY": {"ping", "ban", "kick", "clear", "slowmode", "lock", "unlock", "say", "nick", "nickname", "role", "removerole", "mute", "unmute", "warn", "warnings", "clearwarns", "unwarn", "unban", "purgebots", "purgehumans", "nuke", "antispam", "link", "setlogs"},
    "🎫 SERVER & MANAGEMENT": {"control", "ticket", "add", "ticket-remove", "close", "autorole", "welcome", "giveaway", "refresh", "owner"},
    "👤 INFO & PROFILE": {"serverinfo", "userinfo", "roles", "servericon", "serverbanner", "banner", "rank", "botstats", "uptime", "debug", "invite", "avatar"},
    "🎮 FUN & TOOLS": {"calculator", "ascii", "poll", "quiz", "ship", "coinflip", "roll"},
}


def _help_category(command_name):
    for title, names in _HELP_CATEGORIES.items():
        if command_name in names:
            return title
    return "🧩 OTHER"


def _required_params(command):
    return [p for p in command.parameters if getattr(p, "required", False)]


def _param_type_name(param):
    option_type = getattr(param, "type", None)
    names = {
        3: "دەق",
        4: "ژمارە",
        5: "بەڵێ/نەخێر",
        6: "User / Member ID",
        7: "Channel ID",
        8: "Role ID",
        9: "User/Role ID",
        10: "ژمارەی decimal",
        11: "Attachment",
    }
    return names.get(int(option_type) if option_type is not None else 3, "دەق")


def _command_usage(command):
    parts = [f"`/{command.name}`", f"`$${command.name}`".replace("$$", "$", 1)]
    for param in command.parameters:
        if getattr(param, "required", False):
            parts[0] += f" <{param.name}>"
            parts[1] += f" <{param.name}>"
        else:
            parts[0] += f" [{param.name}]"
            parts[1] += f" [{param.name}]"
    return "  •  ".join(parts)


def _all_help_commands(bot):
    commands_list = [
        c for c in bot.tree.get_commands()
        if isinstance(c, app_commands.Command)
    ]
    commands_list.sort(key=lambda c: (_help_category(c.name), c.name.lower()))
    return commands_list


def _build_help_embed(bot, page):
    commands_list = _all_help_commands(bot)
    page_size = 20
    total_pages = max(1, (len(commands_list) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    current = commands_list[page * page_size:(page + 1) * page_size]

    lines = [
        "✨ **هەر فەرمانێک دوگمەی تایبەتی خۆی هەیە.**",
        "🔹 دەست لە دوگمەی فەرمانەکە بدە بۆ بەکارهێنان.",
        "🔹 ئەگەر فەرمانەکە argument ـی پێویستی هەبێت، فۆڕمێک دەکرێتەوە بۆ نووسینی.",
        "🔹 هەموو فەرمانەکان بە هەردوو شێوازن: `/command` و `$command`.",
        "",
    ]

    last_category = None
    for command in current:
        category = _help_category(command.name)
        if category != last_category:
            lines.append(f"\n**{category}**")
            last_category = category
        required = _required_params(command)
        marker = "📝" if required else "⚡"
        lines.append(f"{marker} **/{command.name}** — {command.description or 'بێ وەسف'}")

    embed = discord.Embed(
        title="🤖 HMB GLOBAL • HELP CENTER",
        description="\n".join(lines)[:4000],
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="⌨️ شێوازی بەکارهێنان",
        value="هەموو command ـەکان: `/command` یان `$command`",
        inline=False,
    )
    embed.set_footer(text=f"Page {page + 1}/{total_pages} • {len(commands_list)} commands • ⚡ direct • 📝 input")
    return embed


async def _resolve_help_value(interaction, param, raw):
    value = str(raw).strip()
    option_type = int(getattr(param, "type", 3))

    if option_type == 3:
        return value
    if option_type == 4:
        return int(value)
    if option_type == 10:
        return float(value)
    if option_type == 5:
        lowered = value.lower()
        if lowered in {"true", "yes", "y", "on", "1", "بەڵێ"}:
            return True
        if lowered in {"false", "no", "n", "off", "0", "نەخێر"}:
            return False
        raise ValueError("تەنها true/false بنووسە.")

    if not interaction.guild:
        raise ValueError("ئەم فەرمانە لە سێروەر بەکاربهێنە.")

    numeric = re.sub(r"[^0-9]", "", value)
    if not numeric:
        raise ValueError(f"بۆ {param.name} ـەکە ID ی دروست بنووسە.")
    object_id = int(numeric)

    if option_type == 6:
        member = interaction.guild.get_member(object_id)
        if member:
            return member
        try:
            return await interaction.guild.fetch_member(object_id)
        except Exception:
            raise ValueError("Member نەدۆزرایەوە.")

    if option_type == 7:
        channel = interaction.guild.get_channel(object_id)
        if channel:
            return channel
        raise ValueError("Channel نەدۆزرایەوە.")

    if option_type == 8:
        role = interaction.guild.get_role(object_id)
        if role:
            return role
        try:
            return await interaction.guild.fetch_role(object_id)
        except Exception:
            raise ValueError("Role نەدۆزرایەوە.")

    if option_type == 9:
        member = interaction.guild.get_member(object_id)
        if member:
            return member
        role = interaction.guild.get_role(object_id)
        if role:
            return role
        raise ValueError("User/Role نەدۆزرایەوە.")

    return value


async def _run_help_command(interaction, command, values=None):
    values = values or {}

    # Respect the same permission/check decorators used by the slash command.
    for check in getattr(command, "checks", []):
        result = check(interaction)
        if inspect.isawaitable(result):
            result = await result
        if not result:
            raise app_commands.CheckFailure("permission check failed")

    kwargs = {}
    for param in command.parameters:
        if param.name in values:
            kwargs[param.name] = await _resolve_help_value(interaction, param, values[param.name])

    callback = command.callback
    await callback(interaction, **kwargs)


class HMBCommandModal(discord.ui.Modal):
    def __init__(self, bot, command, owner_id):
        super().__init__(title=f"/{command.name}"[:45], timeout=180)
        self.bot = bot
        self.command = command
        self.owner_id = owner_id
        self.inputs = {}

        for param in _required_params(command)[:5]:
            text_input = discord.ui.TextInput(
                label=str(param.name)[:45],
                placeholder=f"{_param_type_name(param)} — {param.description or 'بەهاکە بنووسە'}"[:100],
                required=True,
                max_length=1000,
            )
            self.inputs[param.name] = text_input
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ ئەم فۆڕمە بۆ تۆ نییە.", ephemeral=True)
        try:
            values = {name: str(field.value) for name, field in self.inputs.items()}
            await _run_help_command(interaction, self.command, values)
        except app_commands.MissingPermissions:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ ڕێگەت پێنەدراوە بۆ ئەم فەرمانە.", ephemeral=True)
        except app_commands.CheckFailure:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ تەنها بەکارهێنەری ڕێگەپێدراو دەتوانێت ئەم فەرمانە بەکاربهێنێت.", ephemeral=True)
        except Exception as exc:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ فەرمانەکە جێبەجێ نەکرا: `{str(exc)[:700]}`", ephemeral=True)


class HMBHelpView(discord.ui.View):
    def __init__(self, bot, owner_id=None, page=0, persistent=False):
        super().__init__(timeout=None if persistent else 900)
        self.bot = bot
        self.owner_id = owner_id
        self.persistent = persistent
        self.page = page
        self.commands_list = _all_help_commands(bot)
        self.page_size = 20
        self.total_pages = max(1, (len(self.commands_list) + self.page_size - 1) // self.page_size)
        self._build()

    async def interaction_check(self, interaction: discord.Interaction):
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ ئەم Help Menu ـە بۆ کەسی دروستکراوە.", ephemeral=True)
            return False
        return True

    def _build(self):
        self.clear_items()
        start = self.page * self.page_size
        current = self.commands_list[start:start + self.page_size]

        for index, command in enumerate(current):
            required = _required_params(command)
            emoji = "📝" if required else "⚡"
            button = discord.ui.Button(
                label=f"{emoji} /{command.name}"[:80],
                style=discord.ButtonStyle.primary if not required else discord.ButtonStyle.secondary,
                row=index // 5,
                custom_id=f"hmb:help:cmd:{command.name}",
            )

            async def callback(interaction, cmd=command):
                required_params = _required_params(cmd)
                if required_params:
                    await interaction.response.send_modal(
                        HMBCommandModal(self.bot, cmd, self.owner_id)
                    )
                    return
                try:
                    await _run_help_command(interaction, cmd)
                except app_commands.MissingPermissions:
                    if not interaction.response.is_done():
                        await interaction.response.send_message("❌ ڕێگەت پێنەدراوە بۆ ئەم فەرمانە.", ephemeral=True)
                except app_commands.CheckFailure:
                    if not interaction.response.is_done():
                        await interaction.response.send_message("❌ تەنها بەکارهێنەری ڕێگەپێدراو دەتوانێت ئەم فەرمانە بەکاربهێنێت.", ephemeral=True)
                except Exception as exc:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"❌ فەرمانەکە جێبەجێ نەکرا: `{str(exc)[:700]}`", ephemeral=True)

            button.callback = callback
            self.add_item(button)

        previous = discord.ui.Button(label="⬅️ پێشوو", style=discord.ButtonStyle.secondary, disabled=self.page <= 0, row=4, custom_id=f"hmb:help:prev:{self.page}")
        next_button = discord.ui.Button(label="دواتر ➡️", style=discord.ButtonStyle.secondary, disabled=self.page >= self.total_pages - 1, row=4, custom_id=f"hmb:help:next:{self.page}")
        close = discord.ui.Button(label="✖️ داخستن", style=discord.ButtonStyle.danger, row=4, custom_id=f"hmb:help:close:{self.page}")

        async def previous_callback(interaction):
            self.page -= 1
            self._build()
            await interaction.response.edit_message(embed=_build_help_embed(self.bot, self.page), view=self)

        async def next_callback(interaction):
            self.page += 1
            self._build()
            await interaction.response.edit_message(embed=_build_help_embed(self.bot, self.page), view=self)

        async def close_callback(interaction):
            self.stop()
            await interaction.response.edit_message(view=None)

        previous.callback = previous_callback
        next_button.callback = next_callback
        close.callback = close_callback
        self.add_item(previous)
        self.add_item(next_button)
        self.add_item(close)

def register_persistent_help_views(bot):
    if getattr(bot, "_hmb_help_views_registered", False):
        return
    commands_list = _all_help_commands(bot)
    page_size = 20
    total_pages = max(1, (len(commands_list) + page_size - 1) // page_size)
    for page in range(total_pages):
        bot.add_view(HMBHelpView(bot, owner_id=None, page=page, persistent=True))
    bot._hmb_help_views_registered = True


def setup_features(bot):
    # setup_hook should be safe if invoked more than once.
    if getattr(bot, "_hmb_feature_commands_registered", False):
        return
    bot._hmb_feature_commands_registered = True

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

    @bot.tree.command(name="help", description="مێنوی جوانی هەموو فەرمانەکان بە دوگمە")
    async def help_cmd(interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=_build_help_embed(bot, 0),
            view=HMBHelpView(bot, interaction.user.id, 0),
            ephemeral=True,
        )

    @bot.tree.command(name="calculator", description="ژمێریاری")
    async def calculator(interaction: discord.Interaction, expression: str):
        try:
            result = safe_calc(expression)
        except Exception:
            return await interaction.response.send_message("❌ Expression ڕێگەپێنەدراوە.", ephemeral=True)
        await interaction.response.send_message(f"🧮 `{expression}` = **{result}**")
