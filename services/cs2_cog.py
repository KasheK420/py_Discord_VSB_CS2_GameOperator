import discord
from discord.ext import commands
from discord import app_commands
from utils.config import settings
from utils.source_query import get_info, get_players
from utils.rcon_cs2 import rcon_exec
from utils.db import SessionLocal
from models import MapRequest, HelpTicket

SERVER_KEYS = ("surf", "bhop")

def _srv(key: str) -> dict:
    return settings.CS2[key]

def _is_mod(user: discord.abc.User) -> bool:
    role_ids = {r.id for r in getattr(user, "roles", [])}
    allowed = (
        set(settings.roles_from_csv(settings.DISCORD_ADMIN_ROLE_IDS)) |
        set(settings.roles_from_csv(settings.DISCORD_MOD_ROLE_IDS))
    )
    return bool(role_ids & allowed)

class CS2PanelView(discord.ui.View):
    def __init__(self, default="surf", timeout=None):
        super().__init__(timeout=timeout)
        self.server_key = default

    # server toggles
    @discord.ui.button(label="Surf", style=discord.ButtonStyle.primary)
    async def btn_surf(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.server_key = "surf"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Bhop", style=discord.ButtonStyle.primary)
    async def btn_bhop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.server_key = "bhop"
        await interaction.response.edit_message(view=self)

    # actions
    @discord.ui.button(label="Server Info", style=discord.ButtonStyle.secondary)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        s = _srv(self.server_key)
        try:
            info = await get_info(s["host"], s["port"])
            players = await get_players(s["host"], s["port"])
            names = ", ".join(sorted([p.name for p in players])) or "—"
            emb = discord.Embed(title=f"CS2 • {self.server_key.upper()} status", color=discord.Color.green())
            emb.add_field(name="Address", value=f"{s['host']}:{s['port']}", inline=True)
            emb.add_field(name="Map", value=getattr(info, "map_name", "?"), inline=True)
            emb.add_field(name="Players", value=f"{info.player_count}/{info.max_players}", inline=True)
            emb.add_field(name="Player names", value=names[:1024], inline=False)
            await interaction.followup.send(embed=emb, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Failed to query: `{e}`", ephemeral=True)

    @discord.ui.button(label="Server Password", style=discord.ButtonStyle.secondary, row=1)
    async def btn_password(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = _srv(self.server_key)
        pw = s["server_pass"] or "— (no password)"
        await interaction.response.send_message(f"**{self.server_key.upper()} password:** ||{pw}||", ephemeral=True)

    @discord.ui.button(label="Change Map Request", style=discord.ButtonStyle.success, row=1)
    async def btn_change_map(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChangeMapModal(self.server_key))

    @discord.ui.button(label="Admin Help / Ticket", style=discord.ButtonStyle.danger, row=1)
    async def btn_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = interaction.channel
        if not isinstance(ch, (discord.TextChannel, discord.Thread)):
            return await interaction.response.send_message("Unsupported channel.", ephemeral=True)

        roles = []
        roles += [f"<@&{rid}>" for rid in settings.roles_from_csv(settings.DISCORD_ADMIN_ROLE_IDS)]
        roles += [f"<@&{rid}>" for rid in settings.roles_from_csv(settings.DISCORD_MOD_ROLE_IDS)]

        thread = await ch.create_thread(
            name=f"CS2 help • {self.server_key} • {interaction.user.display_name}",
            type=discord.ChannelType.public_thread
        )
        await thread.send(f"{' '.join(roles)} — help requested by <@{interaction.user.id}> for **{self.server_key}**.")
        # store in DB
        async with SessionLocal() as ses:
            ses.add(HelpTicket(server_key=self.server_key, opener_discord_id=interaction.user.id, thread_id=thread.id))
            await ses.commit()
        await interaction.response.send_message("Ticket created — check the new thread.", ephemeral=True)

class ChangeMapModal(discord.ui.Modal, title="Request Map Change"):
    map_name = discord.ui.TextInput(label="Map (e.g., de_mirage)", required=True, max_length=64)

    def __init__(self, server_key: str):
        super().__init__()
        self.server_key = server_key

    async def on_submit(self, interaction: discord.Interaction):
        ch = interaction.channel
        roles = []
        roles += [f"<@&{rid}>" for rid in settings.roles_from_csv(settings.DISCORD_ADMIN_ROLE_IDS)]
        roles += [f"<@&{rid}>" for rid in settings.roles_from_csv(settings.DISCORD_MOD_ROLE_IDS)]

        thread = await ch.create_thread(
            name=f"Map request • {self.server_key} • {self.map_name.value}",
            type=discord.ChannelType.public_thread
        )
        await thread.send(
            f"{' '.join(roles)} — **Map change requested** by <@{interaction.user.id}> on **{self.server_key}** → `{self.map_name.value}`.\n"
            f"Moderators: use `/cs2 changemap server:{self.server_key} map:{self.map_name.value}` to apply."
        )
        # store in DB
        async with SessionLocal() as ses:
            ses.add(MapRequest(server_key=self.server_key, map_name=self.map_name.value,
                               requester_discord_id=interaction.user.id, thread_id=thread.id))
            await ses.commit()
        await interaction.response.send_message("Request posted — thanks!", ephemeral=True)

class CS2Cog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Slash: post the panel (mods only)
    @app_commands.command(name="cs2panel", description="Post the CS2 control panel in this channel (mods only)")
    async def cs2panel(self, interaction: discord.Interaction):
        if not _is_mod(interaction.user):
            return await interaction.response.send_message("No permission.", ephemeral=True)
        emb = discord.Embed(
            title="CS2 Servers • Surf & Bhop",
            description="Use the buttons below to get info, password, open tickets, or request a map change.",
            color=discord.Color.blurple()
        )
        view = CS2PanelView(default="surf")
        await interaction.response.send_message(embed=emb, view=view)

    # Slash: info (ephemeral)
    @app_commands.command(name="cs2info", description="Get server info")
    @app_commands.describe(server="surf or bhop")
    async def cs2info(self, interaction: discord.Interaction, server: str):
        server = server.lower()
        if server not in SERVER_KEYS:
            return await interaction.response.send_message("Use 'surf' or 'bhop'.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        s = _srv(server)
        try:
            info = await get_info(s["host"], s["port"])
            players = await get_players(s["host"], s["port"])
            emb = discord.Embed(title=f"CS2 • {server.upper()}", color=discord.Color.green())
            emb.add_field(name="Address", value=f"{s['host']}:{s['port']}", inline=True)
            emb.add_field(name="Map", value=getattr(info, "map_name", "?"), inline=True)
            emb.add_field(name="Players", value=f"{info.player_count}/{info.max_players}", inline=True)
            if players:
                names = ", ".join(sorted([p.name for p in players]))[:1024]
                emb.add_field(name="Player names", value=names, inline=False)
            await interaction.followup.send(embed=emb, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Failed to query: `{e}`", ephemeral=True)

    # Slash: password (ephemeral)
    @app_commands.command(name="cs2password", description="Show server password (ephemeral)")
    @app_commands.describe(server="surf or bhop")
    async def cs2password(self, interaction: discord.Interaction, server: str):
        server = server.lower()
        if server not in SERVER_KEYS:
            return await interaction.response.send_message("Use 'surf' or 'bhop'.", ephemeral=True)
        pw = _srv(server)["server_pass"] or "— (no password)"
        await interaction.response.send_message(f"**{server.upper()} password:** ||{pw}||", ephemeral=True)

    # Slash (mods): admin action via RCON
    @app_commands.command(name="cs2", description="CS2 admin actions")
    @app_commands.describe(action="changemap", server="surf/bhop", map="e.g. de_mirage")
    async def cs2(self, interaction: discord.Interaction, action: str, server: str, map: str):
        if not _is_mod(interaction.user):
            return await interaction.response.send_message("No permission.", ephemeral=True)
        action = action.lower(); server = server.lower()
        if action != "changemap" or server not in SERVER_KEYS:
            return await interaction.response.send_message("Usage: action=changemap server=surf|bhop map=<map>", ephemeral=True)
        s = _srv(server)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            out = await rcon_exec(s["rcon_host"], s["rcon_port"], s["rcon_pass"], f"changelevel {map}")
            await interaction.followup.send(f"RCON: `{out.strip() or 'ok'}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"RCON failed: `{e}`", ephemeral=True)
