import asyncio
import logging
import os
from typing import Any

import discord
from discord.ext import commands
from fastapi import FastAPI
from pydantic import BaseModel

from utils.config import settings
from utils.db import engine, Base, SessionLocal
from services.cs2_cog import CS2Cog
from services.portal_cog import PortaCog
from services.presence_task import PresenceTasks
from utils.source_query import get_info, get_players

# ----- logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
log = logging.getLogger("main")

# ----- FastAPI
app = FastAPI(title="CS2 Bot API")

class StatusOut(BaseModel):
    server: str
    address: str
    map: str | None
    players: int
    max_players: int
    names: list[str]

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/status/{server}", response_model=StatusOut)
async def status(server: str):
    server = server.lower()
    if server not in ("surf", "bhop"):
        return {"server": server, "address": "", "map": None, "players": 0, "max_players": 0, "names": []}
    s = settings.CS2[server]
    info = await get_info(s["host"], s["port"])
    players = await get_players(s["host"], s["port"])
    names = sorted([p.name for p in players])
    return {
        "server": server,
        "address": f"{s['host']}:{s['port']}",
        "map": getattr(info, "map_name", None),
        "players": getattr(info, "player_count", 0),
        "max_players": getattr(info, "max_players", 0),
        "names": names
    }

# ----- Discord bot
class CS2Bot(commands.Bot):
    def __init__(self):
        # Slash-only, no privileged intents required
        intents = discord.Intents.none()
        intents.guilds = True  # needed for slash commands & guild events
        super().__init__(command_prefix=None, intents=intents)
        self.presence_tasks = None

    async def setup_hook(self) -> None:
        await self.add_cog(CS2Cog(self))
        await self.add_cog(PortaCog(self))
        # sync commands to guild if provided (faster than global)
        if settings.DISCORD_GUILD_ID:
            guild = discord.Object(id=settings.DISCORD_GUILD_ID)
            await self.tree.sync(guild=guild)
            log.info("Slash commands synced to guild %s", settings.DISCORD_GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Slash commands synced globally")
        self.presence_tasks = PresenceTasks(self)

bot = CS2Bot()

# ----- lifecycle
@app.on_event("startup")
async def on_startup():
    log.info("Starting up…")
    # DB: create tables if not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Discord
    token = settings.DISCORD_BOT_TOKEN
    if not token:
        log.error("DISCORD_BOT_TOKEN missing")
        raise SystemExit(1)

    async def runner():
        try:
            await bot.start(token)
        except Exception as e:
            log.exception("Discord failed: %s", e)
            raise

    # run discord in background
    loop = asyncio.get_running_loop()
    loop.create_task(runner())

@app.on_event("shutdown")
async def on_shutdown():
    log.info("Shutting down…")
    await bot.close()
