import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
from sqlalchemy import select, delete

from utils.config import settings
from utils.source_query import get_info, get_players
from utils.rcon_cs2 import rcon_exec
from utils.db import SessionLocal
from models import CS2PanelMessage

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

# ---------- helpers

async def build_status_embed() -> discord.Embed:
    e = discord.Embed(
        title="CS2 Servers — Surf & Bhop",
        description="Live status. Use buttons below for actions.",
        color=discord.Color.blurple()
    )
    for key in SERVER_KEYS:
        s = _srv(key)
        name = key.upper()
        try:
            info = await get_info(s["host"], s["port"])
            players = await get_players(s["host"], s["port"])
            names = ", ".join(sorted([p.name for p in players])) or "—"
            value = (
                f"**Address:** `{s['host']}:{s['port']}`\n"
                f"**Map:** `{getattr(info, 'map_name', '?')}`\n"
                f"**Players:** `{getattr(info, 'player_count', 0)}/{getattr(info, 'max_players', 0)}`\n"
                f"**Names:** {names[:512]}"
            )
            e.add_field(name=f"{name} — ONLINE", value=value, inline=False)
        except Exception as ex:
            e.add_field(
                name=f"{name} — OFFLINE",
                value=f"**Address:** `{s['host']}:{s['port']}`\nCannot query A2S: `{ex}`",
                inline=False
            )
    return e

async def _ephemeral_info(interaction: discord.Interaction, key: str):
    s = _srv(key)
    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
        info = await get_info(s["host"], s["port"])
        players = await get_players(s["host"], s["port"])
        names = ", ".join(sorted([p.name for p in players])) or "—"
        emb = discord.Embed(title=f"{key.upper()} status", color=discord.Color.green())
        emb.add_field(name="Address", value=f"{s['host']}:{s['port']}", inline=True)
        emb.add_field(name="Map", value=getattr(info, "map_name", "?"), inline=True)
        emb.add_field(name="Players", value=f"{info.player_count}/{info.max_players}", inline=True)
        emb.add_field(name="Player names", value=names[:1024], inline=False)
        await interaction.followup.send(embed=emb, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to query: `{e}`", ephemeral=True)

# ---------- UI

class ChangeMapModal(discord.ui.Modal, title="Change Map"):
    map_name = discord.ui.TextInput(label="Map (e.g., de_mirage)", required=True, max_length=64)

    def __init__(self, server_key: str):
        super().__init__()
        self.server_key = server_key

    async def on_submit(self, interaction: discord.Interaction):
        s = _srv(self.server_key)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            out = await rcon_exec(s["rcon_host"], s["rcon_port"], s["rcon_pass"], f"changelevel {self.map_name.value}")
            await interaction.followup.send(f"{self.server_key.upper()} → changelevel `{self.map_name.value}` → `{out.strip() or 'ok'}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"RCON failed: `{e}`", ephemeral=True)

class SayModal(discord.ui.Modal, title="Say (server chat)"):
    text = discord.ui.TextInput(label="Message", required=True, max_length=190)

    def __init__(self, server_key: str):
        super().__init__()
        self.server_key = server_key

    async def on_submit(self, interaction: discord.Interaction):
        s = _srv(self.server_key)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            out = await rcon_exec(s["rcon_host"], s["rcon_port"], s["rcon_pass"], f'say {self.text.value}')
            await interaction.followup.send(f"{self.server_key.upper()} → say → `{out.strip() or 'ok'}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"RCON failed: `{e}`", ephemeral=True)

class RconModal(discord.ui.Modal, title="Custom RCON (mods only)"):
    command = discord.ui.TextInput(label="Command", required=True, max_length=190)

    def __init__(self, server_key: str):
        super().__init__()
        self.server_key = server_key

    async def on_submit(self, interaction: discord.Interaction):
        if not _is_mod(interaction.user):
            return await interaction.response.send_message("No permission.", ephemeral=True)
        s = _srv(self.server_key)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            out = await rcon_exec(s["rcon_host"], s["rcon_port"], s["rcon_pass"], self.command.value)
            await interaction.followup.send(f"{self.server_key.upper()} → `{self.command.value}` → `{out.strip() or 'ok'}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"RCON failed: `{e}`", ephemeral=True)

class PortaView(discord.ui.View):
    def __init__(self, timeout=None):
        super().__init__(timeout=timeout)

    # SURF row
    @discord.ui.button(label="Surf: Info", style=discord.ButtonStyle.secondary, row=0)
    async def surf_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _ephemeral_info(interaction, "surf")

    @discord.ui.button(label="Surf: Password", style=discord.ButtonStyle.secondary, row=0)
    async def surf_pw(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = _srv("surf")
        await interaction.response.send_message(f"**SURF password:** ||{s['server_pass'] or '— (no password)'}||", ephemeral=True)

    @discord.ui.button(label="Surf: Change Map", style=discord.ButtonStyle.primary, row=0)
    async def surf_chmap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChangeMapModal("surf"))

    @discord.ui.button(label="Surf: Restart", style=discord.ButtonStyle.danger, row=0)
    async def surf_restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = _srv("surf")
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            out = await rcon_exec(s["rcon_host"], s["rcon_port"], s["rcon_pass"], "mp_restartgame 1")
            await interaction.followup.send(f"SURF restart → `{out.strip() or 'ok'}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"RCON failed: `{e}`", ephemeral=True)

    @discord.ui.button(label="Surf: Say", style=discord.ButtonStyle.success, row=0)
    async def surf_say(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SayModal("surf"))

    # BHOP row
    @discord.ui.button(label="Bhop: Info", style=discord.ButtonStyle.secondary, row=1)
    async def bhop_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _ephemeral_info(interaction, "bhop")

    @discord.ui.button(label="Bhop: Password", style=discord.ButtonStyle.secondary, row=1)
    async def bhop_pw(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = _srv("bhop")
        await interaction.response.send_message(f"**BHOP password:** ||{s['server_pass'] or '— (no password)'}||", ephemeral=True)

    @discord.ui.button(label="Bhop: Change Map", style=discord.ButtonStyle.primary, row=1)
    async def bhop_chmap(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChangeMapModal("bhop"))

    @discord.ui.button(label="Bhop: Restart", style=discord.ButtonStyle.danger, row=1)
    async def bhop_restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        s = _srv("bhop")
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            out = await rcon_exec(s["rcon_host"], s["rcon_port"], s["rcon_pass"], "mp_restartgame 1")
            await interaction.followup.send(f"BHOP restart → `{out.strip() or 'ok'}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"RCON failed: `{e}`", ephemeral=True)

    @discord.ui.button(label="Bhop: Say", style=discord.ButtonStyle.success, row=1)
    async def bhop_say(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SayModal("bhop"))

    # Tools row
    @discord.ui.button(label="Connect Links", style=discord.ButtonStyle.secondary, row=2)
    async def connect_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        s1 = _srv("surf"); s2 = _srv("bhop")
        msg = (
            f"**Surf**: `steam://connect/{s1['host']}:{s1['port']}`\n"
            f"**Bhop**: `steam://connect/{s2['host']}:{s2['port']}`"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="RCON (mods)", style=discord.ButtonStyle.secondary, row=2)
    async def custom_rcon(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _is_mod(interaction.user):
            return await interaction.response.send_message("No permission.", ephemeral=True)
        await interaction.response.send_modal(RconModal("surf"))

# ---------- Cog

class PortaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.refresh_task.start()

    def cog_unload(self):
        self.refresh_task.cancel()

    @app_commands.command(
        name="cs2panel_porta",
        description="Post or update the CS2 porta panel in this channel (mods only)"
    )
    async def cs2panel_porta(self, interaction: discord.Interaction):
        if not _is_mod(interaction.user):
            return await interaction.response.send_message("No permission.", ephemeral=True)

        ch = interaction.channel
        if not isinstance(ch, discord.TextChannel):
            return await interaction.response.send_message("Run this in a text channel.", ephemeral=True)

        # check existing panel record for this channel
        async with SessionLocal() as ses:
            row = (await ses.execute(
                select(CS2PanelMessage).where(CS2PanelMessage.channel_id == ch.id)
            )).scalar_one_or_none()

        embed = await build_status_embed()
        view = PortaView()

        if row:
            # edit existing message
            try:
                msg = await ch.fetch_message(row.message_id)
                await msg.edit(embed=embed, view=view)
                return await interaction.response.send_message("Panel updated.", ephemeral=True)
            except Exception:
                # message missing — recreate
                pass

        # create new
        sent = await ch.send(embed=embed, view=view)
        async with SessionLocal() as ses:
            await ses.merge(CS2PanelMessage(channel_id=ch.id, message_id=sent.id))
            await ses.commit()
        await interaction.response.send_message("Panel posted.", ephemeral=True)

    @tasks.loop(seconds=30)
    async def refresh_task(self):
        # iterate over all panels and refresh embeds
        async with SessionLocal() as ses:
            rows = (await ses.execute(select(CS2PanelMessage))).scalars().all()

        for row in rows:
            try:
                ch = self.bot.get_channel(row.channel_id)
                if not isinstance(ch, discord.TextChannel):
                    continue
                msg = await ch.fetch_message(row.message_id)
                embed = await build_status_embed()
                await msg.edit(embed=embed, view=PortaView())
                await asyncio.sleep(0.2)  # be polite to rate limits
            except Exception:
                # if message/channel vanished, cleanup
                async with SessionLocal() as ses:
                    await ses.execute(delete(CS2PanelMessage).where(CS2PanelMessage.id == row.id))
                    await ses.commit()

    @refresh_task.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()
